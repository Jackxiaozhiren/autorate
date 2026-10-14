# Audit: the gate the README instructs, measured against what it implies

Produced by `autorate audit` from the committed records file. Every number here is emitted by that command and re-derived by `autorate verify`, which byte-compares this file against a fresh render from the same records in both of its lanes, and by `tests/test_audit.py`; none is typed, and this file carries no timestamp, so a re-run is byte-comparable.

**G2 (§2):** at `confidence >= 0.85`, the measured error among automated decisions against the 15% that sentence implies, and the multiple by which it misses.

- gate compared against: `0.85` (upstream's own gating figure), so the implied error rate is `1 - gate = 0.15`
- bound level: exact Clopper-Pearson, one-sided at `delta = 0.05`, plus the two-sided upper endpoint (the same owner called at `delta / 2`); owned by `tails.clopper_pearson_upper`, never recomputed here
- certification unit: the CASE, never the row. `count_outcome: a case automates only when every one of its records automates`
- which `confidence`: upstream defines the name twice -- laya/common.py:273 (`answer_confidence(p, k) = max(p)`), its docstring calling it the quantity its calibration figures are computed on, and laya/common.py:289 (`confidence_from_probs(p, k) = 1 - H(p)/log k`), its docstring calling that one not calibrated. The sentence this artefact is about reads the response key `confidence`, and it is the second of the two that fills that key: laya/agent.py:684, where the response's `confidence` key is set to `round(confidence_from_probs(p, k), 4)` and `answer_confidence` is set beside it. Which scale the carried value is actually on is measured per slice by `scales.scale_attribution` and printed with each backend below, so each row names both the definition it was read as and the attribution verdict for its own slice. The name is carried on two scales by two harnesses inside upstream's own tree: `research/eval/laya_eval.py:265`, upstream's evaluation harness, writes each case record's `confidence` as `round(float(probs.max()), 6)` -- the evaluation harness -- which is the first definition, while the response key above is filled by the second. A field name therefore does not say which quantity a file holds; only the program that wrote it does, and the `attributed scale` column is this repository's measurement of which one the audited corpus carries.
- risk-coverage curve: spec §7.3 asks for the frontier, not one gate, so each field below prints the sweep `frontier` made over `lambda` at this run's own `delta = 0.05`, bounded by `tails.clopper_pearson_upper` like the table above it. The grid is 0.00, 0.30, 0.60, 0.85, 0.99.

## `jev`

- rows handed over: **959**; audited: **191**; **excluded: 768**
  - 768 rows excluded because gold is None: an unlabelled answer has nothing to compare with, so wrong-by-inequality is an artifact
- slices audited: `jev/choice` 191 rows (64 cases across the audited population)

| field | read as | attributed scale | cases automated | of those, wrong | measured error | implied | multiple | CP upper (1-sided) | CP upper (2-sided) | informative |
|---|---|---|---|---|---|---|---|---|---|---|
| `confidence` | record key scores['reported_confidence'] -- the confidence value upstream itself published for the record's slice | neither | 58 of 64 | 0 | 0.0000 | 0.15 | 0.00x | 0.0503 | 0.0616 | yes |
| `answer_confidence` | records.max_confidence(record.probs) -- mass on the reported answer, p_max = max(probs) | definitional, not attributed: this tool computes it from probs | 59 of 64 | 0 | 0.0000 | 0.15 | 0.00x | 0.0495 | 0.0606 | yes |
| `act_probability` | record key scores['act_probability'] -- upstream's carried act probability (not a confidence scale; not attributed) | definitional, not attributed: this tool computes it from probs | 0 of 64 | 0 | - | 0.15 | - | - | - | - |

Row-level figures beside them, because the denominators are not the same number twice:
- `confidence`: 175 of 191 ROWS automate, 0 of those wrong (row rate 0.0000, multiple 0.00x); 191 of the audited rows carry the field, and their mean value is 0.9548.
  - `confidence`: the case convention moves the count. Published (`count_outcome: a case automates only when every one of its records automates`): 58 cases. Collapsing each case to one row first: max_field_row = 60, first_row = 59, lowest_repeat = 59. The rate in the table is the published convention; the others are measured here, not quoted.

  Risk-coverage curve for `confidence` -- the same population re-measured at every `lambda` on the grid, at this run's `delta = 0.05`. The unit is the CASE, and every ratio names the denominator it divides:

| lambda | implied error (`1 - lambda`) | automated cases (of 64 cases) | of those, wrong | coverage (automated / 64 cases) | measured error (wrong / automated cases) | CP upper (1-sided, `delta = 0.05`) |
|---|---|---|---|---|---|---|
| `0.00` | 1.00 | 64 | 1 | 1.0000 | 0.0156 | 0.0720 |
| `0.30` | 0.70 | 64 | 1 | 1.0000 | 0.0156 | 0.0720 |
| `0.60` | 0.40 | 63 | 0 | 0.9844 | 0.0000 | 0.0464 |
| `0.85` **(the gate above)** | 0.15 | 58 | 0 | 0.9062 | 0.0000 | 0.0503 |
| `0.99` | 0.01 | 35 | 0 | 0.5469 | 0.0000 | 0.0820 |

  - `confidence`: the curve is a description of this rule on this corpus, not a certificate of any point on it. Where the last column sits above the implied error the corpus cannot bound that threshold either, and the row above says so by name.
- `answer_confidence`: 180 of 191 ROWS automate, 0 of those wrong (row rate 0.0000, multiple 0.00x); 191 of the audited rows carry the field, and their mean value is 0.9676.
  - `answer_confidence`: the case convention moves the count. Published (`count_outcome: a case automates only when every one of its records automates`): 59 cases. Collapsing each case to one row first: max_field_row = 61, first_row = 61, lowest_repeat = 61. The rate in the table is the published convention; the others are measured here, not quoted.

  Risk-coverage curve for `answer_confidence` -- the same population re-measured at every `lambda` on the grid, at this run's `delta = 0.05`. The unit is the CASE, and every ratio names the denominator it divides:

| lambda | implied error (`1 - lambda`) | automated cases (of 64 cases) | of those, wrong | coverage (automated / 64 cases) | measured error (wrong / automated cases) | CP upper (1-sided, `delta = 0.05`) |
|---|---|---|---|---|---|---|
| `0.00` | 1.00 | 64 | 1 | 1.0000 | 0.0156 | 0.0720 |
| `0.30` | 0.70 | 64 | 1 | 1.0000 | 0.0156 | 0.0720 |
| `0.60` | 0.40 | 63 | 0 | 0.9844 | 0.0000 | 0.0464 |
| `0.85` **(the gate above)** | 0.15 | 59 | 0 | 0.9219 | 0.0000 | 0.0495 |
| `0.99` | 0.01 | 41 | 0 | 0.6406 | 0.0000 | 0.0705 |

  - `answer_confidence`: the curve is a description of this rule on this corpus, not a certificate of any point on it. Where the last column sits above the implied error the corpus cannot bound that threshold either, and the row above says so by name.
- `act_probability`: 0 of 191 ROWS automate, 0 of those wrong (row rate -, multiple -); 0 of the audited rows carry the field, and their mean value is -.
  - `act_probability`: NOT_APPLICABLE: this backend carries no value for record key scores['act_probability'] on any of the 191 audited rows, so the gate has nothing to read and no error rate exists to report

  Risk-coverage curve for `act_probability` -- the same population re-measured at every `lambda` on the grid, at this run's `delta = 0.05`. The unit is the CASE, and every ratio names the denominator it divides:

| lambda | implied error (`1 - lambda`) | automated cases (of 64 cases) | of those, wrong | coverage (automated / 64 cases) | measured error (wrong / automated cases) | CP upper (1-sided, `delta = 0.05`) |
|---|---|---|---|---|---|---|
| `0.00` | 1.00 | 0 | 0 | 0.0000 | - | - |
| `0.30` | 0.70 | 0 | 0 | 0.0000 | - | - |
| `0.60` | 0.40 | 0 | 0 | 0.0000 | - | - |
| `0.85` **(the gate above)** | 0.15 | 0 | 0 | 0.0000 | - | - |
| `0.99` | 0.01 | 0 | 0 | 0.0000 | - | - |

  - `act_probability`: the curve is a description of this rule on this corpus, not a certificate of any point on it. Where the last column sits above the implied error the corpus cannot bound that threshold either, and the row above says so by name.

- attribution `jev/choice`: **neither** over 191 measured rows of 191 handed over; worst row distance to `max(p)` 0.170000, to the entropy scale 0.157315; per-row mixture both=74 answer_only=23 entropy_only=0 neither=94. The verdict is the batch's worst case, so the mixture is the part that may be read per row.

## `laya`

- rows handed over: **960**; audited: **192**; **excluded: 768**
  - 768 rows excluded because gold is None: an unlabelled answer has nothing to compare with, so wrong-by-inequality is an artifact
- slices audited: `laya/choice` 192 rows (64 cases across the audited population)

| field | read as | attributed scale | cases automated | of those, wrong | measured error | implied | multiple | CP upper (1-sided) | CP upper (2-sided) | informative |
|---|---|---|---|---|---|---|---|---|---|---|
| `confidence` | record key scores['reported_confidence'] -- the confidence value upstream itself published for the record's slice | confidence_entropy | 2 of 64 | 1 | 0.5000 | 0.15 | 3.33x | 0.9747 | 0.9874 | **NO** |
| `answer_confidence` | records.max_confidence(record.probs) -- mass on the reported answer, p_max = max(probs) | definitional, not attributed: this tool computes it from probs | 9 of 64 | 5 | 0.5556 | 0.15 | 3.70x | 0.8312 | 0.8630 | **NO** |
| `act_probability` | record key scores['act_probability'] -- upstream's carried act probability (not a confidence scale; not attributed) | definitional, not attributed: this tool computes it from probs | 64 of 64 | 44 | 0.6875 | 0.15 | 4.58x | 0.7823 | 0.7976 | **NO** |

Row-level figures beside them, because the denominators are not the same number twice:
- `confidence`: 6 of 192 ROWS automate, 3 of those wrong (row rate 0.5000, multiple 3.33x); 192 of the audited rows carry the field, and their mean value is 0.2889.
  - `confidence`: NOT_INFORMATIVE: the exact one-sided upper bound 0.9747 on 2 automated cases is above the 0.15 error rate the gate's own sentence implies, so this corpus cannot bound the gate it is being asked to certify

  Risk-coverage curve for `confidence` -- the same population re-measured at every `lambda` on the grid, at this run's `delta = 0.05`. The unit is the CASE, and every ratio names the denominator it divides:

| lambda | implied error (`1 - lambda`) | automated cases (of 64 cases) | of those, wrong | coverage (automated / 64 cases) | measured error (wrong / automated cases) | CP upper (1-sided, `delta = 0.05`) |
|---|---|---|---|---|---|---|
| `0.00` | 1.00 | 64 | 44 | 1.0000 | 0.6875 | 0.7823 |
| `0.30` | 0.70 | 24 | 16 | 0.3750 | 0.6667 | 0.8220 |
| `0.60` | 0.40 | 9 | 5 | 0.1406 | 0.5556 | 0.8312 |
| `0.85` **(the gate above)** | 0.15 | 2 | 1 | 0.0312 | 0.5000 | 0.9747 |
| `0.99` | 0.01 | 0 | 0 | 0.0000 | - | - |

  - `confidence`: the curve is a description of this rule on this corpus, not a certificate of any point on it. Where the last column sits above the implied error the corpus cannot bound that threshold either, and the row above says so by name.
- `answer_confidence`: 27 of 192 ROWS automate, 15 of those wrong (row rate 0.5556, multiple 3.70x); 192 of the audited rows carry the field, and their mean value is 0.5739.
  - `answer_confidence`: NOT_INFORMATIVE: the exact one-sided upper bound 0.8312 on 9 automated cases is above the 0.15 error rate the gate's own sentence implies, so this corpus cannot bound the gate it is being asked to certify

  Risk-coverage curve for `answer_confidence` -- the same population re-measured at every `lambda` on the grid, at this run's `delta = 0.05`. The unit is the CASE, and every ratio names the denominator it divides:

| lambda | implied error (`1 - lambda`) | automated cases (of 64 cases) | of those, wrong | coverage (automated / 64 cases) | measured error (wrong / automated cases) | CP upper (1-sided, `delta = 0.05`) |
|---|---|---|---|---|---|---|
| `0.00` | 1.00 | 64 | 44 | 1.0000 | 0.6875 | 0.7823 |
| `0.30` | 0.70 | 61 | 41 | 0.9531 | 0.6721 | 0.7710 |
| `0.60` | 0.40 | 25 | 16 | 0.3906 | 0.6400 | 0.7976 |
| `0.85` **(the gate above)** | 0.15 | 9 | 5 | 0.1406 | 0.5556 | 0.8312 |
| `0.99` | 0.01 | 0 | 0 | 0.0000 | - | - |

  - `answer_confidence`: the curve is a description of this rule on this corpus, not a certificate of any point on it. Where the last column sits above the implied error the corpus cannot bound that threshold either, and the row above says so by name.
- `act_probability`: 192 of 192 ROWS automate, 132 of those wrong (row rate 0.6875, multiple 4.58x); 192 of the audited rows carry the field, and their mean value is 1.0000.
  - `act_probability`: NOT_INFORMATIVE: the exact one-sided upper bound 0.7823 on 64 automated cases is above the 0.15 error rate the gate's own sentence implies, so this corpus cannot bound the gate it is being asked to certify

  Risk-coverage curve for `act_probability` -- the same population re-measured at every `lambda` on the grid, at this run's `delta = 0.05`. The unit is the CASE, and every ratio names the denominator it divides:

| lambda | implied error (`1 - lambda`) | automated cases (of 64 cases) | of those, wrong | coverage (automated / 64 cases) | measured error (wrong / automated cases) | CP upper (1-sided, `delta = 0.05`) |
|---|---|---|---|---|---|---|
| `0.00` | 1.00 | 64 | 44 | 1.0000 | 0.6875 | 0.7823 |
| `0.30` | 0.70 | 64 | 44 | 1.0000 | 0.6875 | 0.7823 |
| `0.60` | 0.40 | 64 | 44 | 1.0000 | 0.6875 | 0.7823 |
| `0.85` **(the gate above)** | 0.15 | 64 | 44 | 1.0000 | 0.6875 | 0.7823 |
| `0.99` | 0.01 | 64 | 44 | 1.0000 | 0.6875 | 0.7823 |

  - `act_probability`: the curve is a description of this rule on this corpus, not a certificate of any point on it. Where the last column sits above the implied error the corpus cannot bound that threshold either, and the row above says so by name.

- attribution `laya/choice`: **confidence_entropy** over 192 measured rows of 192 handed over; worst row distance to `max(p)` 0.383700, to the entropy scale 0.000223; per-row mixture both=0 answer_only=0 entropy_only=192 neither=0. The verdict is the batch's worst case, so the mixture is the part that may be read per row.

## What this does and does not establish

- Both halves are results. Where the measured error exceeds the implied error the gate misses its own sentence, and the multiple says by how much. Where the bound sits above the implied error the corpus cannot bound the gate at all, and `NOT_INFORMATIVE` is printed instead of a certificate.
- Which row answers the README: its own instruction (laya/README.md:567-581, `Automated Confidence Gating`: `conf = answers[...]["confidence"]` then `if conf >= 0.85: route_automatically(dept)`) reads the response key `confidence`, which reaches this corpus as `readers/feishu_zh.py`, which stores the archive's `confidence` under the record key `scores["reported_confidence"]`, and upstream fills that key from laya/common.py:289 (`confidence_from_probs(p, k) = 1 - H(p)/log k`) -- the second of the two definitions it publishes under one name, the first being laya/common.py:273 (`answer_confidence(p, k) = max(p)`). So the row that answers that sentence verbatim is **`confidence`**: `jev` 0.00x on 58 of 64 automated cases (0 wrong), one-sided bound 0.0503, informative: yes; `laya` 3.33x on 2 of 64 automated cases (1 wrong), one-sided bound 0.9747, informative: **NO**. The **`answer_confidence`** row is the same instruction read as `p_max = max(probs)` -- upstream's calibrated quantity, a different number on a different scale: `jev` 0.00x on 59 of 64 automated cases (0 wrong), one-sided bound 0.0495, informative: yes; `laya` 3.70x on 9 of 64 automated cases (5 wrong), one-sided bound 0.8312, informative: **NO**. Quoting either multiple as the other is the definition slip the two definitions make possible, and this artefact publishes both rows precisely so a headline can name which one it means. Which of them this corpus bounds is the `informative` column's answer above, row by row.
- A multiple is a point estimate and needs its interval before it is anything else: the widest miss above is `act_probability` at 4.58x, which is 44 wrong out of 64 automated cases, whose exact one-sided upper bound is 0.7823 and whose two-sided upper endpoint is 0.7976. Neither bound is quoted as a certificate of the other.
- Nothing here certifies a deployment: this measures a rule the reference README instructs, on archived responses. The certified bounds live on the certificates, which `autorate report` publishes and `autorate verify` re-derives.
