#!/usr/bin/env bash
# Plan D Task 3: run the gate inside a `git archive` export, and write docs/G5.md from what it printed.
#
#     AUTORATE_G5_CORPUS=<path to the feishu_zh archive> bash tools/g5_export.sh <sha>
#
# The subject is the EXPORT, not the working tree: no `.git`, no corpus inside the repository, no model, and
# no reason a machine-local path could work. `docs/RESULTS.md` already proves the numbers are derived; this
# proves the derivation runs somewhere that cannot see my machine.
#
# Three things make the run more than "it worked when I tried it":
#   * the environment is ASKED (`.git` presence, the export interpreter's own `torch`/`transformers` lookup,
#     and a deliberate fetch that has to fail), because "no model" and "no network" are properties, not
#     intentions;
#   * both lanes run, so the two denominators and the gap between them are printed rather than described;
#   * three falsifications are planted and restored byte-identically, because a green that cannot go red is
#     not evidence.
#
# Scratch paths never reach the transcript: every recorded value passes through `mask`, and
# `tools/g5_transcript.py` refuses to write a document that still matches a machine-path shape. The corpus
# path comes from the environment and is never recorded -- this script must not learn where the archive lives.
set -u

REV=${1:-HEAD}
REPO=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "run me from inside the repository" >&2; exit 2; }
if [ -z "${AUTORATE_G5_CORPUS:-}" ] || [ ! -f "${AUTORATE_G5_CORPUS}/data/manifest.json" ]; then
  echo "AUTORATE_G5_CORPUS must point at a feishu_zh archive containing data/manifest.json. The" >&2
  echo "corpus-present lane is the one that owns the transcribed digests, so a transcript without it" >&2
  echo "would print one number and claim two. Nothing was written." >&2
  exit 2
fi
CORPUS=$AUTORATE_G5_CORPUS
git -C "$REPO" cat-file -e "${REV}^{commit}" 2>/dev/null || { echo "no such commit: $REV" >&2; exit 2; }

WORK=$(mktemp -d "${TMPDIR:-/tmp}/g5-XXXXXX")
EXPORT="$WORK/export"
RECORD="$WORK/record.tsv"
mkdir -p "$EXPORT" "$WORK/home"
: > "$RECORD"

# Both spellings of the scratch path, because macOS resolves its own temp root through `/private`: the
# interpreter reports `sys.prefix` as `/private/var/folders/.../g5-XXXX/...` while `mktemp -d` returned the
# same directory as `/var/folders/...`. Masking only the literal `mktemp` gave a record whose prefix line the
# emitter was right to refuse -- measured, not predicted: the first run of this script stopped here, at the
# emitter, and wrote nothing.
WORK_REAL=$(cd "$WORK" && pwd -P)
mask() { sed -e "s|$WORK_REAL|<export-dir>|g" -e "s|$WORK|<export-dir>|g"; }
put() { # put <dotted.key> <value...> : one masked line per key, so the emitter has a flat schema to read
  # Both halves go to the record: the first `printf` here once wrote the key to stdout and only the value to
  # the file, which is the shape of failure where every recorded value loses the name it is checked by.
  { printf '%s\t' "$1"; shift; printf '%s\n' "$*"; } | mask >> "$RECORD"
}
step() { # step <key-prefix> <human label> <cmd...> : record command, rc and the last output line
  local prefix=$1 label=$2; shift 2
  local out rc
  out=$("$@" 2>&1); rc=$?
  put "$prefix.command" "$label"
  put "$prefix.rc" "$rc"
  put "$prefix.output" "$(printf '%s\n' "$out" | tail -1)"
  LAST_OUTPUT=$out
}

cd "$REPO" || exit 99
git archive --format=tar -o "$WORK/head.tar" "$REV" || { echo "git archive failed" >&2; exit 1; }
tar -C "$EXPORT" -xf "$WORK/head.tar" || { echo "unpack failed" >&2; exit 1; }
git ls-tree -r --name-only "$REV" > "$EXPORT/.tracked-files"

cd "$EXPORT" || exit 99
export HOME="$WORK/home" XDG_CACHE_HOME="$WORK/home/.cache" XDG_CONFIG_HOME="$WORK/home/.config"
export PYTHONDONTWRITEBYTECODE=1 NO_PROXY='*' no_proxy='*'
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 AUTORATE_TRACKED_FILES="$EXPORT/.tracked-files"

uv sync --frozen --extra dev > "$WORK/sync.log" 2>&1 || {
  echo "uv sync failed" >&2; tail -5 "$WORK/sync.log" >&2; exit 1; }
BIN="$EXPORT/.venv/bin/autorate"
PY3="$EXPORT/.venv/bin/python3"

# --- the environment, asked rather than assumed ---------------------------------------------------------
[ -e "$EXPORT/.git" ] && put env.git_dir PRESENT || put env.git_dir ABSENT
SPECS=$($PY3 -c 'import importlib.util as u, sys
print(bool(u.find_spec("torch")), bool(u.find_spec("transformers")), sys.prefix, sep="\n")')
put env.torch "$(printf '%s\n' "$SPECS" | sed -n 1p)"
put env.transformers "$(printf '%s\n' "$SPECS" | sed -n 2p)"
put env.prefix "$(printf '%s\n' "$SPECS" | sed -n 3p)"
put env.toolchain "$(uname -srm) | $($PY3 -V 2>&1) | $(uv --version 2>&1)"
put env.offline_flags "HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 exported for every step, and no step needed them"
put env.digest "$(AUTORATE_TRACKED_FILES="$EXPORT/.tracked-files" $PY3 -c 'from autorate.protocol import load_protocol, protocol_digest; print(protocol_digest(load_protocol("protocol.json")))')"
put env.tracked_files "AUTORATE_TRACKED_FILES written from \`git ls-tree -r --name-only $REV\`," \
  "because the export has no \`.git\` to ask; the path guard takes its subject from that manifest"
curl -sS --max-time 8 https://authorate-g5-nonexistent.invalid/ > "$WORK/net.log" 2>&1
NET=$?
if [ "$NET" -eq 0 ]; then
  put env.network "A FETCH SUCCEEDED (curl rc=0): this transcript may not claim no-network"
else
  put env.network "attempted a DNS-failing HTTPS fetch, and it failed as required (curl rc=$NET)"
fi
put commit "$REV"

# --- the two lanes --------------------------------------------------------------------------------------
AUTORATE_FEISHU_ROOT=/nonexistent-corpus-dir step lane_absent \
  "AUTORATE_FEISHU_ROOT=/nonexistent-corpus-dir autorate verify --protocol protocol.json" \
  "$BIN" verify --protocol protocol.json
AUTORATE_FEISHU_ROOT="$CORPUS" step lane_present \
  "AUTORATE_FEISHU_ROOT=<corpus, supplied by the environment and not recorded> autorate verify --protocol protocol.json" \
  "$BIN" verify --protocol protocol.json

# --- the falsifications, each restored byte-identically --------------------------------------------------
#
# Four plants, and the first one is a finding rather than a demonstration: moving a rubric value inside the
# export's `protocol.json` answers `rc=2` from `load_protocol`, which refuses an internally inconsistent
# freeze BEFORE any published number is compared. That is earlier and stronger than the `rc=4` drift this step
# was written to show, so the drift half is planted separately, at step four, on a value the loader cannot
# veto: a published artefact's stamped digest.
restore_check() { # restore_check <record-prefix> <backup> <target>
  cp "$2" "$3" || { put "$1.restored" "RESTORE FAILED (copy back) for $3"; return; }
  if cmp -s "$2" "$3"; then put "$1.restored" "$3 restored byte-identical"
  else put "$1.restored" "RESTORE FAILED (differs) for $3"; fi
}

cp protocol.json "$WORK/protocol.orig"
sed -i '' 's/"alpha": 0.05/"alpha": 0.07/' protocol.json
AUTORATE_FEISHU_ROOT=/nonexistent-corpus-dir step tamper_protocol \
  "move rubric.alpha to 0.07 in the export's protocol.json (measured: the loader refuses at 2)" \
  "$BIN" verify --protocol protocol.json
restore_check tamper_protocol "$WORK/protocol.orig" protocol.json

cp data/records_feishu.jsonl "$WORK/records.orig"
cp data/records_ordinal_synthetic.jsonl data/records_feishu.jsonl
AUTORATE_FEISHU_ROOT=/nonexistent-corpus-dir step swap_records \
  "replace data/records_feishu.jsonl with another valid self-consistent file (expect rc 4 on the records digest)" \
  "$BIN" verify --protocol protocol.json
restore_check swap_records "$WORK/records.orig" data/records_feishu.jsonl

cp data/inventory.md.json "$WORK/inventory.orig"
printf '[]\n' > data/inventory.md.json
AUTORATE_FEISHU_ROOT=/nonexistent-corpus-dir step wrong_shape_snapshot \
  "put the JSON array [] at data/inventory.md.json (expect rc 4 as a named refusal)" \
  "$BIN" verify --protocol protocol.json
if printf '%s' "$LAST_OUTPUT" | grep -q Traceback; then
  put wrong_shape_snapshot.note "a TRACEBACK escaped -- the exit-code contract was not held"
else
  put wrong_shape_snapshot.note "no traceback in the refusal"
fi
restore_check wrong_shape_snapshot "$WORK/inventory.orig" data/inventory.md.json

cp data/cert_laya.json "$WORK/cert.orig"
$PY3 - <<'INNER'
import json, pathlib
target = pathlib.Path("data/cert_laya.json")
doc = json.loads(target.read_text())
digest = doc["meta"]["protocol_digest"]
doc["meta"]["protocol_digest"] = ("1" if digest[0] == "0" else "0") + digest[1:]
target.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
INNER
AUTORATE_FEISHU_ROOT=/nonexistent-corpus-dir step tamper_artefact_digest \
  "change one hex digit of data/cert_laya.json meta.protocol_digest (expect rc 4 as drift on the stamped meta)" \
  "$BIN" verify --protocol protocol.json
restore_check tamper_artefact_digest "$WORK/cert.orig" data/cert_laya.json

# --- the transcript --------------------------------------------------------------------------------------
"$PY3" "$REPO/tools/g5_transcript.py" --record "$RECORD" --out "$REPO/docs/G5.md"
rc=$?
echo "transcript rc=$rc"
echo "record (masked): $(sed "s|$WORK|<export-dir>|g" "$RECORD" | wc -l | tr -d ' ') keys"
exit $rc
