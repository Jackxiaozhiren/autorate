# Offline data inventory

Produced by `autorate.inventory.write_inventory`; every number here is computed,
not typed. Re-run `uv run --frozen pytest tests/test_inventory.py -q` to reproduce.

- corpus: `/Users/jackson/laya/laya-0.3.20/research/benchmarks/feishu_zh`
- unique ids: **64**   repeats: [0, 1, 2]
- slice keys (families): `conditional`, `cross_chat`, `knowledge`, `lifecycle`, `ownership`, `thread_context`, `untrusted_content`, `urgency`
- label balance: {'urgent': 16, 'todo': 16, 'valuable': 16, 'noise': 16}
- upstream `audit.py` exit code: **0** (interpreter `/Users/jackson/laya/laya-0.3.20/.venv/bin/python`)
- provenance: AI-assisted, manually specified synthetic scenarios inspired by workplace workflows; no private chat logs. Not independently human-annotated.
- upstream `SOURCE.json` file digests: **9/9 match**

## Archive lines per mode x backend

| key | archive lines |
|---|---|
| choice/jev | 192 |
| choice/laya | 192 |
| four_noul/jev | 192 |
| four_noul/laya | 192 |

Counts here are archive LINES per mode and backend, taken before any
quarantine; the reader keeps the lines whose probabilities close, so its
`lines_by_mode` can be smaller (measured: 383 choice lines kept of 384 present).


## Can this corpus support a bound?

Bound width for an automation-rate estimate is `2*sqrt(ln(2/alpha)/(2n))`. At `alpha=0.05` the committed corpus gives **0.3395** for n=64, which is why `autorate certify` is expected to refuse on it rather than publish a number.

| corpus | unique n | bound width @0.05 | feasible @0.10 | note |
|---|---|---|---|---|
| feishu_zh | 64 | 0.3395 | no | paired laya/Jev archived responses, zh, 3 repeats |
| massive_intent_per_language | 2974 | 0.0498 | yes | test/en.json.gz parsed; de and sw also 2974 |
| massive_intent_all_languages | 151674 | 0.0070 | yes | 51 gzipped JSONL files, ~3.2 MB total, Apache-2.0 |
| typed_decisions | not opened | - | - | size category 1K<n<10K from the dataset card; row count not yet opened |

## Known gaps

- research/results/eval_english_51_languages.json: per-case records omitted; regenerate with research/eval/laya_eval.py --langs all --out <path>
- mteb/amazon_massive_intent is not in the local HF dataset cache
- the archived corpus carries no randomisation draw (u), so APS ties resolve to 0 here
- the four `noul` asks carry no per-ask ground truth anywhere in the fixtures (asks ['action', 'related', 'urgent', 'value'] are not among the case keys ['expected', 'family', 'id', 'messages', 'rationale', 'target_id']); only the composite 4-way label is supervised, so a noul certificate on this corpus would certify invented labels
- 1 archived choice line(s) publish probabilities that do not close to 1 within 0.005 and are quarantined by the reader rather than absorbed by a wider tolerance: jev/lifecycle-01/repeat=1 (sum 0.9900)
