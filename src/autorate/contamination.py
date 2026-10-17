"""The contamination probe: a stratified delta-hat with an interval, and a refusal when the strata
are not real.

Plan B3 Task 4. The question is whether the cases used to calibrate a certificate were also inside
training, because if they were, the measured error rate is optimistic -- the model has seen them. The
probe compares the observed error rate of the in-training stratum with that of the fresh stratum:

    delta_hat = R_in - R_out,  R_s = erroneous_cases / automated_cases

and it answers in the only form this project publishes: an estimate WITH its interval and an
interpretation rule. It is a diagnostic, not a proof. A difference between the strata says that the
strata differ; leakage is only one of the reasons two subsets of a corpus can differ, and no
threshold on `delta_hat` is licensed by these numbers, which is why `claim` is False in every result
this module returns -- including the ones whose interval excludes zero.

The envelope, declared rather than assumed:

* **The strata have to be real.** `in_training` must be stated per stratum, must not be constant
  across the pair, must name who declared it and where the declaration lives, and must not name a
  field that exists inside the archive. `in_training = (repeat == 0)` is the cheapest way to make
  this probe run and the specific thing it exists to refuse: three draws of one case against the
  other draws of the same cases is not a comparison, it is one sample pretending to be two
  (`DERIVED_MEMBERSHIP_FIELDS`).
* **The denominators are case counts.** This module counts nothing. It reads the case-denominated
  names `case_count.count_outcome` publishes and refuses a stratum whose counts do not order
  (`erroneous_cases <= automated_cases <= n_eval_cases`), because the committed archive supplies the
  confusion for real: jev carries 96 automated RECORDS over 32 automated CASES, and a rate built on
  the row count would claim three times the evidence (R-36/R-44).
* **The exclusion census has to travel with the stratum.** 1,536 of the 1,919 archived rows are
  `qtype="noul"` and every one of them carries `gold = null`; the certifier excludes them by qtype
  first, so the committed artefacts report `skipped_no_gold = 0` and `skipped_wrong_qtype = 768`.
  The probe requires both counters and prints them. A stratum that states no census either saw only
  eligible rows or filtered something without saying what, and this module cannot tell those apart.
* **The interval is conservative, and says so.** A two-sided interval on a difference of two
  independent rates is built as the Minkowski difference of two exact single-parameter intervals --
  wider than the exact interval on the difference, and stated as such rather than presented as
  tight. The joint level is paid for by `N_PIECES = 4` single-tail claims (two strata, two tails
  each) under the same union-bound shape `certificate.N_CLAIMS` uses for a certificate's three
  claims, and it is deliberately not that number: a certificate's claims and a probe's claims are
  different sets.

Ownership, stated precisely because this module is arithmetic-adjacent to two files it may not edit:

* `tails.py` owns the interval arithmetic -- `clopper_pearson_upper` and the binomial machinery under
  it. This module imports it and re-implements nothing. `tails` provides one tail only, so the
  lower tail is the duality composition `1 - upper(n - k, n, piece)` written at the call site in
  `_exact_two_sided`: a different binomial inverted (the complement count), not a mirrored gap --
  which is the "do not fake a two-sided interval by doubling one tail" rule. A first-class
  `clopper_pearson_lower` in `tails.py` is the missing owner; it is not added here because that
  file belongs to another lane.
* the per-piece level is a union-bound split, `delta / N_PIECES`. `correction.bonferroni` (Plan B3
  Task 2) is the intended owner of that split and does not exist in the tree yet, so the division is
  done here with its piece count named. When Task 2 lands, this is the line that changes.
* `certificate.canonicalise_bound` owns the precision a transcendental-derived *published* number is
  stored at (12 decimals, `PUBLISHED_DECIMALS`), and it ceils -- right for an upper bound, wrong in
  sign for a lower one. Nothing here publishes a number, so nothing here canonicalises one; a
  surface that prints these endpoints later needs the mirrored floor first. No third precision
  constant is introduced here (R-127), and the interpretation line renders integers only, so a case
  count never arrives with a borrowed float precision.

Exit codes, as everywhere in this project (R-115): every refusal here is a `ValueError`, which
`cli.main()` maps to 2 -- a missing declaration, a zero denominator, a thin stratum, a non-mapping
argument. The zero denominator is refused at the raising site rather than left to become
`ZeroDivisionError` (rc 1 is unreachable), and the one arithmetic condition that would mean this
project's own numbers contradicted themselves -- a bound that fails to bracket its own observed
rate -- is `tails.clopper_pearson_upper`'s `ArithmeticError` (4), which this module deliberately does
not catch.
"""
from __future__ import annotations

import re
from typing import Optional

from .certificate import PUBLISHED_DECIMALS
from .tails import clopper_pearson_upper

# --- the declaration contract ---------------------------------------------------------------

#: The meta key that states training membership for a stratum. Nothing in the committed corpus
#: writes it (measured: absent from `data/records_feishu.jsonl` and from both `data/cert_*.json`),
#: which is the reason the probe's refusal path is its real path today.
IN_TRAINING_KEY = "in_training"

#: The companion key that names the source of the declaration. A flag with no source is the
#: caller's expectation, not a stratum.
IN_TRAINING_BY = "in_training_by"

#: What the source block must state, both non-empty: who declared it, and where the declaration is.
BY_FIELDS = ("declared_by", "evidence")

#: This module's own name. A declaration it wrote would certify its own input.
PROBE_OWNER = "autorate.contamination"

#: Fields that live inside the archive and therefore cannot state training membership. `repeat` is
#: the one the brief names -- it is a slice key on all 1,919 committed rows, so `repeat == 0` is the
#: cheapest available fiction -- and `seed`, `u`, `id`, `case_id` are the same trap one field over.
DERIVED_MEMBERSHIP_FIELDS = ("repeat", "seed", "u", "id", "case_id")

_DERIVED_RX = re.compile(
    r"\b(%s)\b" % "|".join(re.escape(field) for field in DERIVED_MEMBERSHIP_FIELDS))

# --- the interval contract --------------------------------------------------------------------

#: The four single-tail claims that pay for the interval: in-training lower, in-training upper,
#: out-of-training lower, out-of-training upper. Counted here, not inherited from the certificate's
#: `N_CLAIMS`, because these are the probe's claims.
N_PIECES = 4

#: The probe's joint tail budget, and therefore each piece's level: `PROBE_DELTA / N_PIECES` = 0.0125.
#: Every piece is under 0.5, which is the condition under which `clopper_pearson_upper` asserts its
#: own bracketing invariant -- so the interval is guaranteed to contain both observed rates with no
#: tolerance of this module's own.
PROBE_DELTA = 0.05

#: The thinnest stratum the probe will read, stated in CASES. Derived, not chosen: at the probe's
#: per-piece level the best case (a stratum with no errors) has a two-sided exact interval spanning
#: 0.19676 at 20 cases and 0.20597 at 19, measured through `tails.clopper_pearson_upper`, so 20 is
#: the smallest case count whose best case is under 0.20. Below it the interval this module would
#: publish is wider than the quantity it is trying to resolve.
MIN_CASES_PER_STRATUM = 20

#: The widest single-stratum interval the probe is willing to print. `MIN_CASES_PER_STRATUM` is its
#: case-count form; one of the two is the rule and the other is its derivation, never both at once.
MAX_STRATUM_INTERVAL_WIDTH = 0.20

#: The case-denominated names this module reads, exactly as `case_count.count_outcome` publishes
#: them. There is no record-denominated denominator available here and no `n_records`.
CASE_COUNT_KEYS = ("automated_cases", "erroneous_cases", "n_eval_cases")

#: The exclusion census a stratum must state. Absence is a refusal, because a silently filtered
#: stratum and a fully eligible one look identical in a rate.
EXCLUSION_KEYS = ("skipped_no_gold", "skipped_wrong_qtype")

#: The certificate fields the two strata must agree on, or delta_hat is a rule change and not a
#: membership difference. `certificate.py`'s subject rule, applied one level up.
COMPARABLE_FIELDS = ("alpha", "beta", "delta", "method", "backend")


# --- helpers ----------------------------------------------------------------------------------

_GRID = 10.0 ** -PUBLISHED_DECIMALS


def _quantise_outward(value: float, side: str) -> float:
    """One transcendental bound, snapped onto `PUBLISHED_DECIMALS` away from the interval's centre.

    `certificate.canonicalise_bound` does this for an upper bound alone. A bracket has two sides, and the
    direction is the content: a lower end rounded UP would publish an interval narrower than the one the
    arithmetic produced, which is exactly the claim this module makes about its own bracket. The grid is
    the same one the published bounds use, so the operation is idempotent -- a value already on the grid
    rounds to itself -- and the most either platform can move a number is one grid step, four orders
    above the last-bit difference that made the first published artefact unreproducible (CI run
    39013012554: `interval_width` 0.05514434488839934 published against 0.055144344888399005 recomputed).
    """
    snapped = round(value, PUBLISHED_DECIMALS)
    if side == "upper" and snapped < value:
        snapped = round(snapped + _GRID, PUBLISHED_DECIMALS)
    elif side == "lower" and snapped > value:
        snapped = round(snapped - _GRID, PUBLISHED_DECIMALS)
    return snapped


def _exact_two_sided(k: int, n: int, piece: float) -> tuple:
    """(lower, upper) exact bounds on a binomial rate at joint level 1 - 4*`piece`.

    The upper is the owner's `clopper_pearson_upper(k, n, piece)`. The lower is the same owner
    applied to the COMPLEMENT count and reflected, `1 - upper(n - k, n, piece)`, which inverts
    `P(X <= n-k | p) = piece` on the other tail -- a second bisection of a different binomial, not
    a mirrored gap. Doubling one tail instead would put the lower end below zero for a small rate,
    where no rate can live; tests/test_contamination.py pins the two apart.

    Both ends are quantised outwards here, at their one source, so everything the probe publishes from
    them -- the Minkowski interval, its width, which end excludes zero -- is a correctly-rounded function
    of grid values and not of a platform's libm. That is `canonicalise_bound`'s rule applied to the
    bracket rather than to a single bound.
    """
    upper = _quantise_outward(clopper_pearson_upper(k, n, piece), "upper")
    lower = _quantise_outward(1.0 - clopper_pearson_upper(n - k, n, piece), "lower")
    return lower, upper


def _name(key: str, stratum) -> str:
    """A refusal prefix that names the stratum the caller keyed it under, and the object behind it.

    Both are printed because a refusal an operator has to act on needs the key they wrote and the
    certificate that answered, and the second one is what shows a stratum that is not a certificate
    at all.
    """
    return "stratum %r (%s)" % (key, type(stratum).__name__)


def _checked_declaration(name: str, meta: dict) -> Optional[bool]:
    """The stratum's declared membership, or a refusal. `None` only when nothing is declared."""
    if IN_TRAINING_KEY not in meta:
        raise ValueError(
            "%s states no %r, and the probe cannot compare strata nobody declared: %s must be "
            "True or False per stratum. Membership inferred from anything inside the archive "
            "(%s) is not a declaration -- in particular a repeat is not a stratum"
            % (name, IN_TRAINING_KEY, IN_TRAINING_KEY, ", ".join(DERIVED_MEMBERSHIP_FIELDS)))
    declared = meta[IN_TRAINING_KEY]
    if declared is None:
        raise ValueError(
            "%s declares %s = None: an unmade declaration is not a stratum, and reading it as "
            "False would compare a guess against itself" % (name, IN_TRAINING_KEY))
    if not isinstance(declared, bool):
        raise ValueError(
            "%s declares %s = %r, which is not a declaration: it must be True or False, and a "
            "string or an integer cannot be separated from a typo here"
            % (name, IN_TRAINING_KEY, declared))
    if IN_TRAINING_BY not in meta:
        raise ValueError(
            "%s states %s without %s: a flag with no source is the caller's expectation, so the "
            "declaration has to name who made it and where it lives"
            % (name, IN_TRAINING_KEY, IN_TRAINING_BY))
    source = meta[IN_TRAINING_BY]
    if not isinstance(source, dict):
        raise ValueError(
            "%s's %s is not a mapping with keys %s: got %r"
            % (name, IN_TRAINING_BY, ", ".join(BY_FIELDS), source))
    missing = [field for field in BY_FIELDS if field not in source]
    if missing:
        raise ValueError("%s's %s is missing %s"
                         % (name, IN_TRAINING_BY, ", ".join(repr(f) for f in missing)))
    text = {}
    for field in BY_FIELDS:
        value = source[field]
        if not isinstance(value, str):
            raise ValueError("%s's %s field %r must be a non-empty string, got %r"
                             % (name, IN_TRAINING_BY, field, value))
        if not value.strip():
            raise ValueError("%s's %s field %r is blank; an empty declaration is not evidence"
                             % (name, IN_TRAINING_BY, field))
        text[field] = value
    if PROBE_OWNER in text["declared_by"]:
        raise ValueError(
            "%s's %s was declared by %s itself: the probe may not certify its own strata, and a "
            "diagnostic that writes its own input measures nothing"
            % (name, IN_TRAINING_KEY, PROBE_OWNER))
    joined = "%s %s" % (text["declared_by"], text["evidence"])
    hit = _DERIVED_RX.search(joined)
    if hit is not None:
        raise ValueError(
            "%s derived %s from %r, a field that lives inside the archive: %s is a draw index, a "
            "seed or an identifier, not a statement about training. Splitting on it puts repeats "
            "of one case on both sides of the comparison"
            % (name, IN_TRAINING_KEY, hit.group(1), hit.group(1)))
    return declared


def _checked_counts(name: str, meta: dict) -> tuple:
    """The stratum's case denominators, or a refusal that names the identity it broke."""
    absent = [k for k in CASE_COUNT_KEYS if k not in meta]
    if absent:
        raise ValueError(
            "%s states no %s, so the probe has no case denominator: it reads the counts "
            "case_count.count_outcome publishes and computes no rate of its own from a record"
            % (name, ", ".join(repr(k) for k in absent)))
    automated = meta["automated_cases"]
    erroneous = meta["erroneous_cases"]
    evaluated = meta["n_eval_cases"]
    for label, value in (("automated_cases", automated), ("erroneous_cases", erroneous),
                         ("n_eval_cases", evaluated)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("%s's %s must be a whole number of cases, got %r"
                             % (name, label, value))
    if not 0 <= erroneous <= automated <= evaluated:
        raise ValueError(
            "%s states %s = %r, %s = %r, %s = %r, which cannot all be case counts: the published "
            "identity is erroneous_cases <= automated_cases <= n_eval_cases. A record count in a "
            "case slot is how three repeats of one observation become three observations on the "
            "committed archive (jev: 96 automated records over 32 automated cases)"
            % (name, "erroneous_cases", erroneous, "automated_cases", automated,
               "n_eval_cases", evaluated))
    return automated, erroneous


def _checked_exclusions(name: str, meta: dict) -> dict:
    """The drop census, required rather than assumed zero."""
    out = {}
    for field in EXCLUSION_KEYS:
        if field not in meta:
            raise ValueError(
                "%s states no %s: a stratum whose eligibility rule filtered rows without saying "
                "how many cannot be compared, because the denominator may already be smaller than "
                "the batch (the committed archive excludes 1,536 of 1,919 rows as unlabelled "
                "qtype=noul cases upstream of any certificate)" % (name, field))
        value = meta[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("%s's %s must be a non-negative count, got %r" % (name, field, value))
        out[field] = value
    return out


def _checked_ids(name: str, meta: dict) -> list:
    """The case ids the stratum was measured on, so the pair can be proved disjoint."""
    if "eval_ids" not in meta:
        raise ValueError(
            "%s states no eval_ids, so the probe cannot show that the two strata are disjoint, and "
            "an overlap would put one observation on both sides of a difference" % (name,))
    ids = meta["eval_ids"]
    if isinstance(ids, (str, bytes)) or not isinstance(ids, (list, tuple, set)):
        raise ValueError("%s's eval_ids must be a sequence of ids, got %r"
                         % (name, type(ids).__name__))
    return list(ids)


def _checked_certificate(key: str, stratum) -> dict:
    """One stratum's evidence, read from a certificate this module does not construct."""
    meta = getattr(stratum, "meta", None)
    if not isinstance(meta, dict):
        raise ValueError(
            "the probe reads certificates: stratum %r (%s) carries no meta mapping, so it states "
            "no case counts and no membership declaration" % (key, stratum))
    return meta


# --- the probe --------------------------------------------------------------------------------

def stratified(certificates_by_stratum, delta: float = PROBE_DELTA) -> dict:
    """Compare the observed error rates of a declared in-training stratum and a declared fresh one.

    `certificates_by_stratum` maps a caller's stratum name to a `Certificate` for that stratum. The
    names are the caller's; which stratum is `in` and which is `out` comes from the declaration,
    never from the key -- a mapping called {"in": ..., "out": ...} whose flags say otherwise is
    refused rather than relabelled.

    Returns a dict with `R_in`, `R_out`, `delta_hat`, a two-sided `interval` (conservative: the
    Minkowski difference of two exact single-parameter intervals at `delta / N_PIECES` per piece),
    the case denominators and their rates' own bounds, the exclusion census, the declaration as
    stated, `worse` (which stratum has the higher observed error rate), the sign a contamination
    signature would show, an `interpretation` line, and `claim` -- which is False always.

    Refusals, all `ValueError` (exit 2), in the order a reader should have to hear them: nothing
    declared, one stratum or more than two (a third would be an uncorrected worst-of-G), a constant
    declaration, a derived one, a self-declared one, a pair from different rules, a stratum with no
    case denominator or counts that do not order, a stratum with no exclusion census, strata sharing
    a case, a stratum with no automated case, and a stratum thinner than `MIN_CASES_PER_STRATUM`
    cases. Nothing is averaged away and nothing is dropped quietly.
    """
    if isinstance(delta, bool) or not isinstance(delta, (int, float)):
        raise ValueError("delta must be a number in (0,1), got %r" % (delta,))
    if not 0.0 < float(delta) < 1.0:
        raise ValueError("delta must be in (0,1): it is the tail budget of the interval, got %r"
                         % (delta,))
    delta = float(delta)
    if not isinstance(certificates_by_stratum, dict):
        raise ValueError("stratified takes a mapping of stratum name to certificate; got %r"
                         % (type(certificates_by_stratum).__name__,))
    if not certificates_by_stratum:
        raise ValueError("stratified takes two declared strata; the mapping it was given is empty")
    keys = list(certificates_by_stratum)

    declared: dict = {}
    metas: dict = {}
    problems = []
    for key in keys:
        stratum = certificates_by_stratum[key]
        name = _name(key, stratum)
        meta = _checked_certificate(key, stratum)
        metas[key] = meta
        try:
            declared[key] = _checked_declaration(name, meta)
        except ValueError as problem:
            # every stratum is asked, so a caller fixing this one round sees all of them;
            # the type is kept, because the refusal is still a usage error and not a new class
            problems.append(str(problem))
    if problems:
        raise ValueError("; ".join(problems))

    if len(keys) != 2:
        raise ValueError(
            "the probe compares exactly two strata and was given %d (%s): a third would need the "
            "multiplicity correction this module does not carry, and a worst-of-%d without it is a "
            "false claim (spec 8.1). Pairwise comparisons of three strata would be two "
            "uncorrected claims wearing one name"
            % (len(keys), ", ".join(repr(k) for k in keys), len(keys)))
    if declared[keys[0]] == declared[keys[1]]:
        raise ValueError(
            "the two strata declare a constant %s (%r and %r for %s, %s): one sample cut in two is "
            "one sample, and delta_hat between a stratum and itself is a degeneracy, not a "
            "diagnostic" % (IN_TRAINING_KEY, declared[keys[0]], declared[keys[1]], keys[0], keys[1]))
    in_key = keys[0] if declared[keys[0]] else keys[1]
    out_key = keys[1] if in_key == keys[0] else keys[0]
    in_cert, out_cert = certificates_by_stratum[in_key], certificates_by_stratum[out_key]
    in_name, out_name = _name(in_key, in_cert), _name(out_key, out_cert)

    for field in COMPARABLE_FIELDS:
        left, right = getattr(in_cert, field), getattr(out_cert, field)
        if left != right:
            raise ValueError(
                "%s and %s are not comparable: they differ in %s (%r vs %r). delta_hat would then "
                "be a change of rule and not a difference in membership, and two numbers from two "
                "rules are not a pair" % (in_name, out_name, field, left, right))

    automated_in, erroneous_in = _checked_counts(in_name, metas[in_key])
    automated_out, erroneous_out = _checked_counts(out_name, metas[out_key])
    exclusions = {
        "in": _checked_exclusions(in_name, metas[in_key]),
        "out": _checked_exclusions(out_name, metas[out_key]),
    }
    ids_in = _checked_ids(in_name, metas[in_key])
    ids_out = _checked_ids(out_name, metas[out_key])
    shared = sorted({str(i) for i in ids_in} & {str(i) for i in ids_out})
    if shared:
        raise ValueError(
            "%s and %s share %d case id(s), so they are not two strata: %s. One case inside both "
            "strata puts a single observation on both sides of the difference, which is leakage "
            "in the comparison itself rather than a finding about it"
            % (in_name, out_name, len(shared), ", ".join(shared[:5])))

    for label, name, automated in (("in", in_name, automated_in),
                                   ("out", out_name, automated_out)):
        if automated == 0:
            raise ValueError(
                "%s has no automated case, so R_%s has no denominator: an error rate over nothing "
                "is undefined, not 0.0, and a difference built on an undefined term would be a "
                "number with no observation behind it" % (name, label))
        if automated < MIN_CASES_PER_STRATUM:
            raise ValueError(
                "%s is too thin for the probe: %d cases is below the floor of %d cases (the floor "
                "is the case-count form of a %g maximum single-stratum interval width, measured at "
                "the probe's own per-piece level). Refusing the stratum is the result; averaging it "
                "into a pair would move delta_hat on evidence that cannot resolve it"
                % (name, automated, MIN_CASES_PER_STRATUM, MAX_STRATUM_INTERVAL_WIDTH))

    piece = delta / N_PIECES
    r_in = erroneous_in / automated_in
    r_out = erroneous_out / automated_out
    lower_in, upper_in = _exact_two_sided(erroneous_in, automated_in, piece)
    lower_out, upper_out = _exact_two_sided(erroneous_out, automated_out, piece)
    interval = (lower_in - upper_out, upper_in - lower_out)
    delta_hat = r_in - r_out
    if delta_hat > 0.0:
        worse = "in"
    elif delta_hat < 0.0:
        worse = "out"
    else:
        worse = "neither"
    feasible = {"in": bool(in_cert.feasible), "out": bool(out_cert.feasible)}

    detail = [
        "delta_hat = R_in - R_out over the two declared strata (%s in, %s out): this is a "
        "diagnostic with an interpretation rule, not a proof of leakage" % (in_key, out_key),
        "case denominators: %d cases with %d erroneous in-training against %d with %d "
        "out-of-training; the two rates are those quotients and nothing else was counted here"
        % (automated_in, erroneous_in, automated_out, erroneous_out),
        "the interval is conservative: a Minkowski difference of two exact single-parameter "
        "intervals paid for by %d tail pieces, so it is wider than the exact interval on the "
        "difference" % N_PIECES,
        "%s observed rate is the worse one; the signature contamination would predict is the "
        "out-of-training stratum worse, i.e. delta_hat < 0, and neither direction is a proof"
        % ("The in-training stratum's" if worse == "in" else
           "The out-of-training stratum's" if worse == "out" else "Neither stratum's"),
        "membership was declared, not inferred: %s; %s"
        % (_source(metas[in_key]), _source(metas[out_key])),
        "excluded upstream and named rather than dropped quietly: in-training "
        "skipped_no_gold=%d skipped_wrong_qtype=%d, out-of-training skipped_no_gold=%d "
        "skipped_wrong_qtype=%d"
        % (exclusions["in"]["skipped_no_gold"], exclusions["in"]["skipped_wrong_qtype"],
           exclusions["out"]["skipped_no_gold"], exclusions["out"]["skipped_wrong_qtype"]),
        "no threshold on delta_hat is licensed by these numbers, so claim is False: a difference "
        "says the strata differ, and leakage is one of several reasons they could",
    ]
    if not all(feasible.values()):
        refused = [label for label in ("in", "out") if not feasible[label]]
        detail.append("the %s stratum's own certificate refused, so this delta compares "
                      "observations and not certified rules" % " and ".join(refused))
    interpretation = "; ".join(detail)

    return {
        "strata": {"in": in_key, "out": out_key},
        "R_in": r_in,
        "R_out": r_out,
        "delta_hat": delta_hat,
        "interval": interval,
        "n_cases_in": automated_in,
        "n_cases_out": automated_out,
        "erroneous_cases_in": erroneous_in,
        "erroneous_cases_out": erroneous_out,
        "evaluated_cases_in": metas[in_key]["n_eval_cases"],
        "evaluated_cases_out": metas[out_key]["n_eval_cases"],
        "rate_lower_in": lower_in,
        "rate_upper_in": upper_in,
        "rate_lower_out": lower_out,
        "rate_upper_out": upper_out,
        "worse": worse,
        "expected_under_contamination": "the out-of-training stratum worse than the in-training "
                                        "one, i.e. delta_hat < 0",
        "delta": delta,
        "piece": piece,
        "n_pieces": N_PIECES,
        "level": 1.0 - delta,
        "exclusions": exclusions,
        "declaration": {"in": metas[in_key].get(IN_TRAINING_BY),
                        "out": metas[out_key].get(IN_TRAINING_BY)},
        "feasible": feasible,
        "reason": {"in": in_cert.reason, "out": out_cert.reason},
        "min_cases_per_stratum": MIN_CASES_PER_STRATUM,
        "interpretation": interpretation,
        "claim": False,
    }


def _source(meta: dict) -> str:
    """The declaration's source block, flattened into the interpretation line."""
    source = meta.get(IN_TRAINING_BY)
    if not isinstance(source, dict):
        return "no source stated"
    return "%s declares %s" % (source.get("declared_by", "?"), source.get("evidence", "?"))


def from_counts(in_stratum: dict, out_stratum: dict, delta: float = PROBE_DELTA) -> dict:
    """The same gap, the same interval and the same refusals, taken from two aggregates.

    `stratified` takes certificates, because the probe was designed to be run on records this repository
    scored itself. The only in-training-versus-held-out census that exists at all is upstream's own per-suite
    result file, which publishes `n` and `accuracy` and no per-case probabilities, so no certificate can be
    built from it. This is the door for that case: it takes `(errors, cases)` per stratum and reuses
    `_exact_two_sided`, so the piece budget, the level and the reflected lower tail keep the one owner they
    have in `stratified`, and `claim` stays False here too -- a gap between two aggregate rates is a signal to
    go and read the strata, never a finding of leakage.

    Refusals are `ValueError` (exit 2), and each names the stratum it is complaining about: a count that is
    not a whole number, errors above cases, a stratum thinner than `MIN_CASES_PER_STRATUM`, and a gap whose
    interval is wider than `MAX_STRATUM_INTERVAL_WIDTH` -- the last one is refused rather than printed,
    because an interval that wide cannot exclude zero and the row would read as a measurement of nothing.
    """
    if isinstance(delta, bool) or not isinstance(delta, (int, float)):
        raise ValueError("delta must be a number in (0,1), got %r" % (delta,))
    if not 0.0 < float(delta) < 1.0:
        raise ValueError("delta must be in (0,1): it is the tail budget of the interval, got %r"
                         % (delta,))
    delta = float(delta)
    piece = delta / N_PIECES

    out: dict = {"strata": {}, "claim": False, "delta": delta, "piece": piece,
                 "n_pieces": N_PIECES}
    rates: dict = {}
    for name, stratum in (("in_stratum", in_stratum), ("out_stratum", out_stratum)):
        if not isinstance(stratum, dict):
            raise ValueError("%s must be a mapping with 'errors' and 'cases'; got %r"
                             % (name, type(stratum).__name__))
        errors, cases = stratum.get("errors"), stratum.get("cases")
        for label, value in (("errors", errors), ("cases", cases)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("%s: %s must be a whole number of cases, got %r" % (name, label, value))
        if errors > cases:
            raise ValueError("%s: %d errors over %d cases is not a rate; the counts do not order"
                             % (name, errors, cases))
        if cases < MIN_CASES_PER_STRATUM:
            raise ValueError("%s: %d cases is below the published floor of %d, so pooling it would hide a "
                             "stratum too thin to bound" % (name, cases, MIN_CASES_PER_STRATUM))
        low, high = _exact_two_sided(errors, cases, piece)
        rates[name] = errors / cases
        out["strata"][name] = {"errors": errors, "cases": cases, "rate": rates[name],
                               "bounds": (low, high),
                               "label": stratum.get("label", name),
                               "sources": list(stratum.get("sources", ()))}

    out["R_in"] = rates["in_stratum"]
    out["R_out"] = rates["out_stratum"]
    out["delta_hat"] = rates["in_stratum"] - rates["out_stratum"]
    in_low, in_high = out["strata"]["in_stratum"]["bounds"]
    out_low, out_high = out["strata"]["out_stratum"]["bounds"]
    interval = (in_low - out_high, in_high - out_low)
    out["interval"] = interval
    out["cases"] = {"in_stratum": out["strata"]["in_stratum"]["cases"],
                    "out_stratum": out["strata"]["out_stratum"]["cases"]}
    width = interval[1] - interval[0]
    out["interval_width"] = width
    if width > MAX_STRATUM_INTERVAL_WIDTH:
        raise ValueError("the gap's interval is %s wide, above the published ceiling of %s, so it cannot "
                         "exclude zero and is not a measurement of anything: %s"
                         % (width, MAX_STRATUM_INTERVAL_WIDTH, interval))
    worse = "in_stratum" if out["R_in"] >= out["R_out"] else "out_stratum"
    out["worse"] = worse
    out["sign"] = ("in-training worse" if worse == "in_stratum" else "held-out worse")
    out["excludes_zero"] = interval[0] > 0.0 or interval[1] < 0.0
    out["interpretation"] = (
        "the in-training stratum errs %s than the held-out stratum by %.6f, and the interval %s %s zero; "
        "this is a diagnostic with an interpretation rule, not a proof of leakage: the two strata are carried "
        "by different suites, so the gap is confounded with which tasks sit on which side of the flag"
        % ("more" if worse == "in_stratum" else "less", abs(out["delta_hat"]),
           "[%0.6f, %0.6f]" % interval, "excludes" if out["excludes_zero"] else "contains"))
    return out
