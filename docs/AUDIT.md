# Audit: the gate the README instructs, measured against what it implies

Produced by `autorate audit` from the committed records file. Every number here is emitted by that command and re-derived by `tests/test_audit.py` from the same records; none is typed, and this file carries no timestamp, so a re-run is byte-comparable.

**G2 (§2):** at `confidence >= 0.85`, the measured error among automated decisions against the 15% that sentence implies, and the multiple by which it misses.

- gate compared against: `0.85` (upstream's own gating figure), so the implied error rate is `1 - gate = 0.15`
- bound level: exact Clopper-Pearson, one-sided at `delta = 0.05`, plus the two-sided upper endpoint (the same owner called at `delta / 2`); owned by `tails.clopper_pearson_upper`, never recomputed here
- certification unit: the CASE, never the row. `count_outcome: a case automates only when every one of its records automates`
- which `confidence`: obligation #31 records that upstream defines it two ways, so each field below names the definition it was read as, and the row whose value is a published key names the attribution verdict `scales.scale_attribution` reaches for its own slice.

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
- `answer_confidence`: 180 of 191 ROWS automate, 0 of those wrong (row rate 0.0000, multiple 0.00x); 191 of the audited rows carry the field, and their mean value is 0.9676.
  - `answer_confidence`: the case convention moves the count. Published (`count_outcome: a case automates only when every one of its records automates`): 59 cases. Collapsing each case to one row first: max_field_row = 61, first_row = 61, lowest_repeat = 61. The rate in the table is the published convention; the others are measured here, not quoted.
- `act_probability`: 0 of 191 ROWS automate, 0 of those wrong (row rate -, multiple -); 0 of the audited rows carry the field, and their mean value is -.
  - `act_probability`: NOT_APPLICABLE: this backend carries no value for record key scores['act_probability'] on any of the 191 audited rows, so the gate has nothing to read and no error rate exists to report

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
- `answer_confidence`: 27 of 192 ROWS automate, 15 of those wrong (row rate 0.5556, multiple 3.70x); 192 of the audited rows carry the field, and their mean value is 0.5739.
  - `answer_confidence`: NOT_INFORMATIVE: the exact one-sided upper bound 0.8312 on 9 automated cases is above the 0.15 error rate the gate's own sentence implies, so this corpus cannot bound the gate it is being asked to certify
- `act_probability`: 192 of 192 ROWS automate, 132 of those wrong (row rate 0.6875, multiple 4.58x); 192 of the audited rows carry the field, and their mean value is 1.0000.
  - `act_probability`: NOT_INFORMATIVE: the exact one-sided upper bound 0.7823 on 64 automated cases is above the 0.15 error rate the gate's own sentence implies, so this corpus cannot bound the gate it is being asked to certify

- attribution `laya/choice`: **confidence_entropy** over 192 measured rows of 192 handed over; worst row distance to `max(p)` 0.383700, to the entropy scale 0.000223; per-row mixture both=0 answer_only=0 entropy_only=192 neither=0. The verdict is the batch's worst case, so the mixture is the part that may be read per row.

## What this does and does not establish

- Both halves are results. Where the measured error exceeds the implied error the gate misses its own sentence, and the multiple says by how much. Where the bound sits above the implied error the corpus cannot bound the gate at all, and `NOT_INFORMATIVE` is printed instead of a certificate.
- A multiple is a point estimate and needs its interval before it is anything else: the widest miss above is `act_probability` at 4.58x, which is 44 wrong out of 64 automated cases, whose exact one-sided upper bound is 0.7823 and whose two-sided upper endpoint is 0.7976. Neither bound is quoted as a certificate of the other.
- Nothing here certifies a deployment: this measures a rule the reference README instructs, on archived responses. The certified bounds live on the certificates, which `autorate report` publishes and `autorate verify` re-derives.
