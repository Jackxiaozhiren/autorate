# The contamination gap (G4's second named output)

Written by `python3 tools/contamination_probe.py --out data/contamination_probe.json --doc docs/CONTAMINATION.md --force` and re-checked by `python -m autorate.cli
verify`, which pools the pinned rows again and refuses a disagreement. The pin is committed, so
both lanes produce these bytes; what the corpus-absent lane cannot do is re-digest the upstream
file the pin came from, and the document says that rather than implying otherwise.

Spec section 9 defines this quantity: run the same model over the strata its own harness
declares in-training and held-out, publish the gap with a two-sided interval, and label it a
diagnostic with an interpretation rule -- not a proof of leakage. `claim` is false in the
artefact because no aggregate gap licenses a leakage finding, and the two strata are carried by
different suites, which means task difficulty is confounded with the flag.

- pin: `data/pin_app_benchmark.json` from `research/results/app_benchmark_results.json`, sha256 `15a7ba8a4d123cd1de499ef8036d14ce52e25bfb2bf6ac1d03702135d79c0a05`, 12514 bytes, 27 rows, 4 interval pieces
- budget it answers at: delta=0.05, floor 20 cases per stratum, ceiling 0.2 interval width
- `in_stratum` (`in_training=True`): 15 pinned rows, 1150 errors over 6000 cases
- `out_stratum` (`in_training=False`): 12 pinned rows, 2049 errors over 4800 cases
- excluded from the pin by name: 3 row(s) -- `/suites/app.model_routing_domain/english`, `/suites/app.model_routing_domain/multilingual`, `/suites/app.model_routing_domain/typed-decisions`, each publishing a rounded rate whose `accuracy x n` is not a whole number

| quantity | value |
|---|---|
| `R_in` (in-training error rate) | 0.191666666667 |
| `R_out` (held-out error rate) | 0.426875 |
| `delta_hat = R_in - R_out` | -0.235208333333 |
| two-sided interval | [-0.262646017928, -0.20750167304] |
| interval excludes zero | True |
| stratum with the higher rate | `out_stratum` |
| sign | `held-out worse` |
| `claim` | False |

The interpretation rule, stated because the number without it would be read as a finding:

> the in-training stratum errs less than the held-out stratum by 0.235208, and the interval [-0.262646, -0.207502] excludes zero; this is a diagnostic with an interpretation rule, not a proof of leakage: the two strata are carried by different suites, so the gap is confounded with which tasks sit on which side of the flag

Read as: the in-training stratum errs more, across 15 in-training rows and 12 held-out ones; that is the opposite of the direction a contamination signature predicts. The two
strata are different suites, so the gap is confounded with task difficulty: it bounds a
difference between two aggregate rates and does not show that any checkpoint was trained on any
of these cases.

## Reproducing it

```
AUTORATE_FEISHU_ROOT=<corpus> python3 tools/contamination_pin.py --out data/pin_app_benchmark.json
python3 tools/contamination_probe.py --out data/contamination_probe.json --doc docs/CONTAMINATION.md --force
```
