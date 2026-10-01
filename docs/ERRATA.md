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

## 2026-10-01 — commit `a106cd2` quoted the wrong test count, again

The body says `62 passed`; the gate printed `63 passed in 0.56s` on that tree. This is the
second occurrence within minutes of the first entry, so it is a habit rather than a typo:
commit messages were being written from the most recent run I had seen rather than the one
the commit describes.

**Rule adopted (ledger R-16): commit messages no longer quote suite counts at all.** A count
in prose has no owner and goes stale the moment a test is added; the count that matters is the
one `pytest` prints when CI runs it, and any *number published as a result* must be produced
by the code that reports it (Constraint 12), which Task 9's `verify` enforces. Not amended;
this entry is the correction.


Design prose stated that gating at `confidence >= 0.85` corresponds to `p_max >= ~0.93`
for a four-option question, implying the requirement loosens as the option count grows.
## 2026-10-01 — an entropy-confidence figure was wrong in both value and direction

Measured by bisection over `autorate.records.entropy_confidence`:

| gate | k=2 | k=4 | k=10 | k=20 | k=51 |
|---|---|---|---|---|---|
| `confidence >= 0.85` | 0.9785 | 0.9609 | 0.9427 | 0.9319 | 0.9203 |
| `confidence >= 0.50` | 0.8900 | 0.8107 | 0.7379 | 0.6990 | 0.6611 |

So the `0.93` value belongs to **k=20**, the requirement is **stricter at small k**, and a
`0.93` answer over four options scores `0.7616` — it does not clear the documented gate.
Corrected in the plan's Task 4 test, added as spec §7.4, and now produced by
`tests/test_records.py::_pmax_reaching` rather than quoted from prose.
