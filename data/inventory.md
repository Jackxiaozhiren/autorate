# Offline data inventory

Produced by `uv run --frozen autorate snapshot` -- every number here is computed
from the corpus or opened from a file, and the count basis is named per row.

- corpus: `laya-0.3.20/research/benchmarks/feishu_zh`
- unique ids: **64**   repeats: [0, 1, 2]
- slice keys (families): `conditional`, `cross_chat`, `knowledge`, `lifecycle`, `ownership`, `thread_context`, `untrusted_content`, `urgency`
- label balance: noise=16, todo=16, urgent=16, valuable=16
- upstream `audit.py` exit code: **0** (the interpreter that ran it is recorded in `inventory.md.json`, because it is a path on one machine and stale for every other reader)
- provenance: AI-assisted, manually specified synthetic scenarios inspired by workplace workflows; no private chat logs. Not independently human-annotated.
- upstream `SOURCE.json` file digests: **9/9 match**

## Archive lines per mode x backend

| key | archive lines |
|---|---|
| choice/jev | 191 |
| choice/laya | 192 |
| four_noul/jev | 192 |
| four_noul/laya | 192 |

Counts here are archive LINES per mode and backend, for the lines this pass
could bucket: a line it could not read, or one the shared line rule refused, is
counted beside the table rather than inside it, which is what the reader does with
the same bytes. The reader keeps only the lines it turns into records, so its own
count can still be smaller; what it did with the rest is named on its own line
below rather than netted into a single difference.

- choice: **383 of 384** lines kept by the reader (1 quarantined for this mode)
- four_noul: **384 of 384** lines kept by the reader (0 quarantined for this mode)
- reader dispositions: 0 malformed lines, 1 named by mode, 0 refused (status not ok), 0 filtered


## Can this corpus support a bound?

Bound width for an automation-rate estimate is `2*sqrt(ln(2/alpha)/(2n))`. At `alpha=0.05` the committed corpus gives **0.3395** for n=64, which is why `autorate certify` is expected to refuse on it rather than publish a number.

The bound is computed on `n_independent`, never on `n_rows`: rows that are
repeats or translations of the same case do not add sample size.

| corpus | n_independent | n_rows | count basis | bound width @0.05 | feasible @0.10 |
|---|---|---|---|---|---|
| feishu_zh | 64 | - | scanned from results/v1/{laya,jev}/raw.jsonl | 0.3395 | no |
| massive_intent_per_language | 2974 | 2974 | each of the data/massive_provenance.json pinned test shards opened and counted, 2974 rows per shard | 0.0498 | yes |
| massive_intent_all_languages | 2974 | 151674 | 51 of 51 pinned shards opened, hashed and row-counted on 2026-10-06 at revision 940fd47a81eaa7f2cc7b129674d945d618ac38c2; the digests live in data/massive_provenance.json and the bytes are not vendored | 0.0498 | yes |
| typed_decisions | not opened | - | dataset card size category 1K<n<10K only; no file opened | - | - |

| corpus | unit | note |
|---|---|---|
| feishu_zh | unique labelled cases, each answered twice per backend over 3 repeats | the only corpus with real archived jev responses |
| massive_intent_per_language | labelled decision rows (one utterance, one intent) | each language file is a candidate Mondrian slice |
| massive_intent_all_languages | (language, utterance) pairs -- NOT independent cases | Apache-2.0, 3.2 MB of pinned bytes; the extra shards are translations of the same utterances, so the row multiple is coverage, not sample size |
| typed_decisions | labelled decisions | candidate contamination probe (public train 300 / test 100) |

## Known gaps

- research/results/eval_english_51_languages.json: per-case records omitted; regenerate with research/eval/laya_eval.py --langs all --out <path>
- mteb/amazon_massive_intent is not in the local HF dataset cache
- the archived corpus carries no randomisation draw (u), so APS ties resolve to 0 here
- the four `noul` asks carry no per-ask ground truth anywhere in the fixtures (asks ['action', 'related', 'urgent', 'value'] are not among the case keys ['expected', 'family', 'id', 'messages', 'rationale', 'target_id']); only the composite 4-way label is supervised, so a noul certificate on this corpus would certify invented labels
- 1 archived choice line(s) publish probabilities that do not close to 1 within 0.005 and are quarantined by the reader rather than absorbed by a wider tolerance: jev/lifecycle-01/repeat=1 (sum 0.9900)
- 1 archive line(s) sit outside the per-mode counts (0 unreadable, 1 readable but refused by the line rule the reader owns); the first 1 are named in `lines_outside_mode_counts` with backend, line number and reason: jev line 269 id=lifecycle-01 (probabilities do not close to 1 within tolerance)
