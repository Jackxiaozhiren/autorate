"""The shared choice-record factory, with one owner across Plans B1-B3 (ruling R-69).

Every module in `tests/` that needs a decision record builds its own: `test_certify_choice.py`
has `_records`, `test_certify_threshold.py`, `test_gate.py` and `test_records.py` have `_rec`,
`test_scales.py` has `_choice`. That is right for shape-specific fixtures -- a sweep over
difficulties is that file's business and nobody else's. What was missing is the one shape all
three B-plans need and none of them should redefine: a labelled choice record with a given `id`,
`case_id`, `repeat` and `slices`. Left unowned, each plan writes its own version, and a fixture
shaped by the consumer that uses it certifies a fiction -- it satisfies the assertions of the file
that made it and nothing else. So this module exists, under the name R-69 fixes, and the
certificate-producing tests reuse it rather than inventing a second way to build a record.

It builds REAL `autorate.records.Record` objects through the public constructor and nothing else,
so every validation a corpus row passes is a validation a fixture passes: option/probability
agreement, the probability sum, the gold label on the ballot, `u` in [0, 1), and the
copy-not-adopt freeze on the three mappings (`records.py:119-121`). A stand-in object with the
same attribute names would pass the grouping assertions here and then fail -- or worse, quietly
skip -- the moment a certifier called a `Record` property on it.

Every parameter is keyword-only, which is the lesson `_thresholds.py` records after one of its
solvers survived a review round with two positional parameters transposed: an `id` and a `case_id`
are the same shape and can trade places without any assertion noticing, and the only fix that holds
for EVERY value pair is to make the swap a `TypeError` at the call site.
"""
from autorate.records import Record

# "gold was not passed" must be expressible separately from "this record has no gold label",
# because the second one is a case under test (a certifier's eligibility rule), not a default.
_DERIVE = object()


def _leftmost_argmax(options, probs):
    """The option with the largest probability, ties to the leftmost index.

    The same rule `certify_threshold._submitted_label` uses for a record that states no answer, so
    a bare `choice_record(...)` is a decision whose label and its argmax agree -- and a fixture that
    mirrors production's tie rule cannot drift from it.
    """
    return list(options)[max(range(len(probs)), key=lambda j: probs[j])]


def choice_record(*, id="r0", case_id=None, repeat=0, backend="synthetic", options=None,
                  probs=None, gold=_DERIVE, predicted=None, slices=None, scores=None,
                  seed=0, u=0.0, meta=None) -> Record:
    """One `qtype="choice"` record, valid by construction.

    Defaults are chosen so a bare call is something a certifier can actually certify, and so that
    nothing here claims provenance it does not have:

    * `probs` defaults to (0.7, 0.1, 0.1, 0.1) over `opt0..opt3`, and `options` follows `probs`
      when not given -- one vector, one ballot, never two owners of the option count.
    * `gold` defaults to the ballot's argmax, so a bare call is a CORRECT decision. A fixture that
      cannot be wrong cannot be shown refusing one (`test_certify_choice.py` learned that the hard
      way); pass `gold=` for the wrong ones and `gold=None` for an unlabelled one.
    * `predicted` defaults to None -- "this record states no answer", which is a real upstream
      shape and whose fallback the rule owns, not the fixture.
    * `backend` defaults to "synthetic". It does NOT default to a shipped backend's name: a
      fixture that says `laya` is claiming provenance the data does not have, and `backend` is a
      published certificate field.
    * `case_id` defaults to None, which makes the record its own case (`case_key` falls back to
      `id`). Repeats pass the shared `case_id` explicitly, because the whole point of the field is
      that three rows can stand for one observation.
    """
    vector = tuple(probs) if probs is not None else (0.7, 0.1, 0.1, 0.1)
    ballot = tuple(options) if options is not None else tuple("opt%d" % j for j in range(len(vector)))
    label = _leftmost_argmax(ballot, vector) if gold is _DERIVE else gold
    return Record(id=id, qtype="choice", backend=backend, repeat=repeat,
                  options=ballot, probs=vector, gold=label, predicted=predicted,
                  case_id=case_id, slices=dict(slices or {}), scores=dict(scores or {}),
                  seed=seed, u=u, meta=dict(meta or {}))
