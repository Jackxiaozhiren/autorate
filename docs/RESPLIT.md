# The 200-resplit experiment (G1's second column)

Written by `python -m tools.resplit_experiment` and re-checked by `python -m autorate.cli
verify`, which reads the artefact below and refuses it at exit 4 if it is absent or inconsistent.
No figure here is typed: each is read out of `data/resplit_200.json`, and the document carries no
timestamp so a re-run is byte-comparable in both lanes.

- splits per task: 200
- rubric the experiment ran at: alpha 0.050, beta 0.050, delta 0.050, method `aps`, seed 7
- tasks: 7 (the 6 published decision tasks this repository certifies, plus one synthetic control whose labels are known)

| task | splits certified | refusals | violations / certificates | empirical violation rate |
|---|---|---|---|---|
| `jev` | 0 of 200 | empty_feasible_set:200 | 0 / 0 | undefined (no certificates) |
| `laya` | 0 of 200 | empty_feasible_set:200 | 0 / 0 | undefined (no certificates) |
| `massive/de` | 0 of 200 | empty_feasible_set:200 | 0 / 0 | undefined (no certificates) |
| `massive/en` | 0 of 200 | empty_feasible_set:200 | 0 / 0 | undefined (no certificates) |
| `massive/km` | 0 of 200 | empty_feasible_set:200 | 0 / 0 | undefined (no certificates) |
| `massive/sw` | 0 of 200 | empty_feasible_set:200 | 0 / 0 | undefined (no certificates) |
| `synthetic/sharp-k4-e0.02` | 200 of 200 | - | 0 / 200 | 0.000 |

The rate is the empirical check G1's own column names: a violation is a certified split whose
gold set escapes the bound that split published. It is undefined where no certificate exists -- no
number is imputed, and a `0.000` appears only for a population that does certify. The 6 published tasks refuse in every split at this rubric, which is why the criterion's first column
(`>=3 certified decision tasks`) is unmet and why this table is evidence about the refusal, not
against it. The synthetic row is a control on the machinery, labelled synthetic in the artefact's
own `label`, and is not cited as a decision task G1 counts.
