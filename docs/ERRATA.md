# Errata

Corrections to numbers this project published and then measured differently. Kept as a
tracked file because the rule is that a quoted count must be the count the tool printed.

## 2026-10-01 — commit `e386c08` message quoted the wrong test count

The commit body says `45 passed overall`. The full-suite gate printed:

```
46 passed in 0.42s
```

The 45 was summed from an earlier focused run instead of read off the suite output. The
commit was not amended (it is local and unpushed, and history is preferred over message
accuracy); this entry is the correction, and the ledger repeats the measured number.

## 2026-10-01 — an entropy-confidence figure was wrong in both value and direction

Design prose stated that gating at `confidence >= 0.85` corresponds to `p_max >= ~0.93`
for a four-option question, implying the requirement loosens as the option count grows.
Measured by bisection over `autorate.records.entropy_confidence`:

| gate | k=2 | k=4 | k=10 | k=20 | k=51 |
|---|---|---|---|---|---|
| `confidence >= 0.85` | 0.9785 | 0.9609 | 0.9427 | 0.9319 | 0.9203 |
| `confidence >= 0.50` | 0.8900 | 0.8107 | 0.7379 | 0.6990 | 0.6611 |

So the `0.93` value belongs to **k=20**, the requirement is **stricter at small k**, and a
`0.93` answer over four options scores `0.7616` — it does not clear the documented gate.
Corrected in the plan's Task 4 test, added as spec §7.4, and now produced by
`tests/test_records.py::_pmax_reaching` rather than quoted from prose.
