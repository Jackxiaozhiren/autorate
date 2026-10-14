"""Plan D Task 6: `docs/upstream/` is prepared text that has not been submitted, and these rows are
what makes that statement checkable instead of a promise in prose.

The directory holds an issue, a four-finding patch against a clean `v0.3.20` checkout, a PR
description, the conditional `awesome-jev` entry, and `SUBMISSION.md`. None of it can be policed by
importing anything: it is text about another repository. So each row asks a question the text can
answer the wrong way, and each docstring names the mutation that makes the row red:

1. `test_the_upstream_directory_holds_the_five_named_artefacts` -- delete or rename any artefact.
2. `test_no_artefact_carries_a_machine_absolute_path` -- write a home-, account- or scratch-shaped
   absolute path into any artefact; the non-vacuity half plants one in a file the scanner is pointed
   at, so a pattern that has stopped matching cannot pass as a clean directory.
3. `test_no_artefact_carries_a_secret_shaped_string` -- paste a token-shaped literal.
4. `test_every_cited_claim_id_resolves_to_a_verified_ledger_row` -- cite an id the ledger does not
   carry, or cite `id=guard-preset-overlap` from a line that does not say it is withdrawn.
5. `test_no_artefact_quotes_a_number_from_the_withdrawn_observation` -- paste one of the withdrawn
   figures into `pr-description.md`. This is the row that makes "a prepared artefact may not soften a
   withdrawn claim" a measurement rather than an intention.
6. `test_section_7_1_reproduction_conditions_are_measured_not_assumed` -- break the probe itself
   (point the records probe at a file that does not exist, or the patch at a directory): the row
   refuses a verdict it cannot support rather than defaulting to "met".
7. `test_the_withdrawal_sentences_are_present_because_a_condition_is_unmet` -- delete either
   required sentence from `pr-description.md` or `SUBMISSION.md`, or add a hedge from the softening
   list ("partially supports", "may become citable", "supports the shape of").
8. `test_the_patch_applies_to_a_clean_checkout_without_touching_it` -- reorder or reword a hunk so
   the context no longer matches the tag blobs, or write into the source tree while checking.
9. `test_submission_carries_the_do_not_submit_line_and_the_dated_queries` -- drop the approval line,
   the two-PR order, or a query block's date stamp.
10. `test_the_awesome_jev_entry_is_either_backed_or_omitted_with_its_reason` -- replace the omission
    record with an entry whose claims name no verified ledger row.

What is deliberately NOT claimed here: that the read-only queries still return what they returned on
2026-10-14. They are transcripts with dates, and `SUBMISSION.md` says which ones must be re-run
before anything is filed. A row that re-ran them would need the network the gate otherwise forbids.

The artefact root is overridable (`AUTORATE_UPSTREAM_ARTIFACTS`) so a falsification can plant a
defect in a copy and leave the published directory byte-identical; unset, every row walks the real
thing.
"""
import hashlib
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UPSTREAM = Path(os.environ.get("AUTORATE_UPSTREAM_ARTIFACTS") or (REPO / "docs" / "upstream"))
LEDGER = REPO / "docs" / "VERIFICATION.md"
DATA = REPO / "data"
PATCH_NAME = "laya-0.3.20-fixes.patch"
REQUIRED = ("issue.md", "pr-description.md", "SUBMISSION.md", "awesome-jev-entry.md",
            "patch/" + PATCH_NAME)

# Built from pieces so this file is never the offender it looks for, which is the convention
# `tests/test_cli.py` already uses for its `/` + "Users/bob/x" literal.
MACHINE_PATH_RX = re.compile(r"/(?:Users|home|var/folders|private)/[A-Za-z0-9._-]+/")
SECRET_RX = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{8,}|sk-[A-Za-z0-9]{16,}"
    r"|AKIA[0-9A-Z]{16}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|xox[abprs]-[A-Za-z0-9-]{8,}"
    r"|(?:api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[A-Za-z0-9_\-]{12,}",
    re.IGNORECASE)
CITATION_RX = re.compile(r"(?<![\w-])id=([a-z0-9][a-z0-9-]*)")
SENTENCE_SPLIT_RX = re.compile(r"(?<=[.!?])\s+")
LEDGER_ROW_RX = re.compile(r"^\|\s*id=([a-z0-9][a-z0-9-]*)\s*\|.*?\bstatus:\s*(\w+)", re.MULTILINE)

# The withdrawn observation's own figures (ledger row `guard-preset-overlap`, spec section 7.1). They
# are reproducible from the private note, so a draft can leak one by pasting; none of them may appear
# in the prose of a prepared artefact while the reproduction is unfinished. The patch file itself is
# scoped out -- its fixtures carry measured values and SUBMISSION.md says so -- which is why
# `prose_artefacts()` and `all_artefacts()` are different functions and not one loop.
WITHDRAWN_FIGURES = ("24/24", "11/15", "2/24", "0.786", "0.90-2.42", "0.90\u20132.42", "0.39-1.66",
                     "0.39\u20131.66", "0.973", "0.819", "1.989", "1.762", "1.412", "0.564")

# Sentences spec 7.1 requires once a reproduction condition is unmet, and the hedges that would turn
# a withdrawal back into a claim by degrees.
WITHDRAWAL_SENTENCES = ("the claim stays `withdrawn`", "the report does not quote it")
SOFTENINGS = ("partially supports", "may become citable", "supports the shape of",
              "provisionally verified", "re-verified as established")

PRISTINE_PROBE = ("pyproject.toml", 'onnx = ["onnx", "onnxruntime"]')
PATCH_TARGETS = ("pyproject.toml", "laya/integrations/langchain.py",
                 "tests/test_langchain.py", "tests/test_packaging.py")


def all_artefacts() -> list:
    """Every file under the artefact root, patch included."""
    assert UPSTREAM.is_dir(), "no artefact root at %s" % UPSTREAM
    return sorted(p for p in UPSTREAM.rglob("*") if p.is_file())


def prose_artefacts() -> list:
    """The files whose sentences are the claim: everything but the diff itself."""
    return [p for p in all_artefacts() if p.suffix != ".patch"]


def text(rel: Path) -> str:
    return (UPSTREAM / rel).read_text(encoding="utf-8")



def scan_paths(path: Path) -> list:
    """Machine-absolute path shapes in one file, as (line number, matched text)."""
    home = str(Path.home()) + "/"
    hits = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if home in line:
            hits.append((i, "this machine's home directory"))
        else:
            m = MACHINE_PATH_RX.search(line)
            if m:
                hits.append((i, m.group(0)))
    return hits


def scan_secrets(path: Path) -> list:
    hits = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        m = SECRET_RX.search(line)
        if m:
            hits.append((i, m.group(0)))
    return hits


def ledger_statuses() -> dict:
    """`{id: status}` for every row the ledger actually carries, parsed the way the ledger gate parses."""
    return {m.group(1): m.group(2) for m in LEDGER_ROW_RX.finditer(LEDGER.read_text(encoding="utf-8"))}


def sentences(body: str) -> list:
    """The prose units a citation can hide inside. Hard-wrapped markdown first, then split on ends."""
    return [s for s in SENTENCE_SPLIT_RX.split(re.sub(r"\s+", " ", body)) if s.strip()]


def citations(path: Path) -> list:
    """(id, sentence) for every `id=...` in one artefact, scoped to its SENTENCE.

    Not its line: these files are wrapped at eighty columns, so a rule keyed on the physical line would
    be a formatting demand -- it would force every withdrawn citation onto one line while telling
    nothing about whether the text around it marks the status. The sentence is the smallest unit that
    can carry "this is withdrawn", which is the thing being policed.
    """
    body = path.read_text(encoding="utf-8", errors="ignore")
    out = []
    for sent in sentences(body):
        for m in CITATION_RX.finditer(sent):
            out.append((m.group(1), sent.strip()))
    return out



def _clean_source() -> tuple:
    """Locate a PRISTINE `v0.3.20` tree, as (kind, path), or (None, what was looked for).

    Resolution order: `AUTORATE_LAYA_V0320` (a directory, a tag zip or an sdist tarball), then the
    first ancestor of this checkout that carries a `laya-0.3.20` sibling -- the same no-absolute-
    literal convention `cli._default_corpus` uses, widened because a linked worktree sits two levels
    below the repository that owns the sibling. A directory only counts when its `pyproject.toml`
    still reads `onnx = ["onnx", "onnxruntime"]`: the vendored checkout on this machine carries the
    author's own patch, so a tree that has it is not the clean checkout spec 7.1 asks about, and
    pretending otherwise would let condition (a) be "measured" against bytes the patch already
    touched.
    """
    env = os.environ.get("AUTORATE_LAYA_V0320")
    cands = []
    if env:
        cands.append(Path(env))
    here = REPO
    for ancestor in [here] + list(here.parents)[:4]:
        cands += sorted(ancestor.glob("laya-0.3.20.zip"))
        cands += sorted(ancestor.glob("laya-0.3.20.tar.gz"))
        cands += sorted(ancestor.glob("laya-0.3.20"))
    for c in cands:
        if c.is_dir():
            probe = c / PRISTINE_PROBE[0]
            if probe.is_file() and PRISTINE_PROBE[1] in probe.read_text(encoding="utf-8",
                                                                       errors="ignore"):
                return "dir", c
        elif c.suffix == ".zip" and zipfile.is_zipfile(str(c)):
            return "zip", c
        elif c.name.endswith(".tar.gz") and tarfile.is_tarfile(str(c)):
            return "tar", c
    return None, [str(c) for c in cands]


def _stage_clean_copy(dest: Path) -> tuple:
    """Copy the patch's four target files out of a pristine source into `dest`.

    Returns (staged_dir, None) or (None, why). Read-only on the source by construction: a zip and a
    tarball are read through their archives, a directory through `shutil.copyfile`, and nothing is
    ever written back. The staging is what lets `git apply --check` run outside the corpus.
    """
    kind, source = _clean_source()
    if kind is None:
        return None, "no pristine source among %s" % source
    dest.mkdir(parents=True, exist_ok=True)
    if kind == "zip":
        with zipfile.ZipFile(str(source)) as zf:
            names = set(zf.namelist())
            prefix = sorted({n.split("/")[0] for n in names if n})[0] + "/"
            for rel in PATCH_TARGETS:
                if prefix + rel not in names:
                    return None, "the archive carries no %s" % rel
                (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                (dest / rel).write_bytes(zf.read(prefix + rel))
    elif kind == "tar":
        with tarfile.open(str(source)) as tf:
            names = set(tf.getnames())
            prefix = sorted({n.split("/")[0] for n in names if "/" in n})[0] + "/"
            for rel in PATCH_TARGETS:
                if prefix + rel not in names:
                    return None, "the tarball carries no %s" % rel
                member = tf.extractfile(prefix + rel)
                (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                (dest / rel).write_bytes(member.read())
    else:
        for rel in PATCH_TARGETS:
            f = source / rel
            if not f.is_file():
                return None, "the tree has no %s" % rel
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(f), str(dest / rel))
    return dest, None


def _scratch_root() -> Path:
    """Where a scratch copy may be staged: `AUTORATE_T6_SCRATCH` when set, else the runner's temp dir.

    The plan tells this task to keep its scratch outside `/tmp` as an artefact home, so an operator who
    wants the staged copy inspected sets the variable and reads it back from the failure message; a
    CI lane that sets nothing still gets a directory that writes nothing to the corpus.
    """
    env = os.environ.get("AUTORATE_T6_SCRATCH")
    root = Path(env) if env else Path(tempfile.mkdtemp(prefix="t6-scratch-"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _fingerprint(path: Path) -> tuple:
    st = path.stat()
    return (hashlib.sha256(path.read_bytes()).hexdigest(), st.st_mtime_ns, st.st_size)


def _apply_check(scratch: Path) -> tuple:
    """`git apply --check` the checked-in patch inside `scratch`; returns (rc, output)."""
    patch = UPSTREAM / "patch" / PATCH_NAME
    p = subprocess.run(["git", "apply", "--check", "-p1", str(patch)],
                       capture_output=True, text=True, cwd=str(scratch))
    return p.returncode, (p.stdout + p.stderr).strip()


def _guardrail_records_present() -> bool:
    """Condition (b): are the guard prompts and their labels committed as per-case records?

    Streams every committed record file line by line and stops at the first hit, so the answer is about
    the whole corpus rather than a head sample. The needle is the guardrail question id the ranges
    belong to (`harm_severity`) or a record id in the guard set (`guard-`): whichever the reproduction
    used, a committed per-case record would carry one of them.
    """
    needles = ("harm_severity", '"id": "guard-', '"id":"guard-')
    files = sorted(DATA.glob("*.jsonl")) + sorted(DATA.glob("*.json"))
    if not files:
        raise AssertionError("no record files under %s -- the probe cannot answer, which is not "
                             "the same as the condition being unmet" % DATA)
    for f in files:
        with f.open(encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if any(n in line for n in needles):
                    return True
    return False



def _verify_rederives_ranges() -> bool:
    """Condition (c): does anything `autorate verify` re-derives name the guardrail quantities?

    `verify` re-derives the values its protocol and `report.py` tables name. If neither the frozen
    protocol nor any tool source mentions the guardrail question the ranges belong to, then no run of
    the gate can re-derive them -- which is the measurement spec 7.1 asks for, not a guess about it.
    """
    hay = [(REPO / "protocol.json").read_text(encoding="utf-8", errors="ignore")]
    sources = sorted((REPO / "src" / "autorate").rglob("*.py"))
    assert sources, "no tool sources under src/autorate -- refusing to call condition (c) unmet " \
                    "on a probe that read nothing"
    hay += [py.read_text(encoding="utf-8", errors="ignore") for py in sources]
    joined = "\n".join(hay)
    return "harm_severity" in joined or "guard_questions" in joined


def test_the_upstream_directory_holds_the_five_named_artefacts():
    """Mutation: delete or rename any file in `REQUIRED`, and this row goes red by name.

    The plan names five artefacts; a directory that holds three of them and a confident
    `SUBMISSION.md` is exactly the failure this repository has twice documented in itself --
    the plan marking its own homework.
    """
    assert UPSTREAM.is_dir(), "docs/upstream/ does not exist at %s" % UPSTREAM
    missing = [rel for rel in REQUIRED if not (UPSTREAM / rel).is_file()]
    assert not missing, "missing artefacts: %s" % missing
    files = all_artefacts()
    assert files, "the directory exists but holds no files"
    for f in files:
        assert f.stat().st_size > 0, "empty artefact %s" % f.relative_to(UPSTREAM)
        b = f.read_bytes()
        assert b.decode("utf-8"), "not utf-8: %s" % f.relative_to(UPSTREAM)


def test_no_artefact_carries_a_machine_absolute_path():
    """Mutation: write `/` + `Users/<name>/x` (or a home, account or scratch root) into any artefact.

    `tests/test_cli.py`'s guard walks `git ls-files`, which does not see an untracked directory until
    it is committed -- so this task cannot rely on it for its own artefacts. The scan is also wider
    than that guard on purpose: `docs/upstream/` quotes commands a reviewer runs in a scratch copy,
    and the scratch root is the shape most likely to be pasted in full.
    """
    offenders = [(str(f.relative_to(UPSTREAM)), scan_paths(f)) for f in all_artefacts()]
    offenders = [(p, hits) for p, hits in offenders if hits]
    assert not offenders, offenders
    # Non-vacuity, asserted on built shapes rather than assumed from a clean directory: the same
    # convention `tests/test_cli.py` uses for its `/` + "Users/bob/x" literal.
    assert MACHINE_PATH_RX.search("/" + "Users/bob/x"), "the guard is vacuous"
    assert MACHINE_PATH_RX.search("/" + "var/folders/5l/nltc5k/T/scratch/x"), "the scratch class"
    assert not MACHINE_PATH_RX.search("see <scratch>/laya-0.3.20 for the copy"), "placeholder prose"


def test_the_path_scan_reports_a_planted_machine_path(tmp_path):
    """Mutation: break the scanner (drop a shape from the pattern) and the plant stops being caught.

    The published artefacts must stay byte-identical while a falsification runs, so the plant lands on
    a copy in `tmp_path` and the same scanner runs over it.
    """
    for shape in ("/" + "Users/dev/scratch/laya-0.3.20", "/" + "home/dev/scratch/x",
                  "/" + "var/folders/5l/nltc5k/T/g5-Ab12Cd", "/" + "private/tmp/laya-0.3.20"):
        f = tmp_path / "artefact.md"
        f.write_text("run it in %s/pyproject.toml\n" % shape, encoding="utf-8")
        assert scan_paths(f), "the scanner missed %r" % shape
        f.write_text("run it in <scratch>/pyproject.toml\n", encoding="utf-8")
        assert scan_paths(f) == [], "the placeholder itself is being reported"


def test_no_artefact_carries_a_secret_shaped_string():
    """Mutation: paste a token-shaped literal (a `ghp_...`, a private key block, an api_key= value).

    The queries this task records are read-only GitHub calls made with an authenticated client, and a
    transcript of an authenticated session is where a token gets copied by accident.
    """
    offenders = [(str(f.relative_to(UPSTREAM)), scan_secrets(f)) for f in prose_artefacts()]
    offenders = [(p, hits) for p, hits in offenders if hits]
    assert not offenders, offenders
    assert SECRET_RX.search("ghp_" + "ABCDEFGH12345678"), "the secret guard is vacuous"
    assert SECRET_RX.search("access_token" + ": " + "z" * 24), "an assigned token must be caught"
    assert not SECRET_RX.search("Token scopes are listed by `gh auth status`, redacted there")


def test_every_cited_claim_id_resolves_to_a_verified_ledger_row():
    """Mutation: cite an id the ledger does not carry, or cite a withdrawn id in a sentence that never
    says the word `withdrawn`.

    The ledger's header rule is that a claim is `verified` with a URL and a date or `withdrawn` with a
    `dropped:`/`replaced:` note, and there is no third state. A prepared artefact is the place a
    citation most easily decays into a bare name, so membership is checked against the parsed ledger,
    and a non-`verified` id is allowed only inside a sentence that says so in the ledger's own word.
    """
    statuses = ledger_statuses()
    assert statuses, "the ledger parsed to nothing; the citation gate would pass vacuously"
    bad = []
    for f in prose_artefacts():
        for cid, sent in citations(f):
            status = statuses.get(cid)
            if status is None:
                bad.append((str(f.relative_to(UPSTREAM)), cid, sent[:120], "not in the ledger"))
            elif status != "verified" and "withdrawn" not in sent:
                bad.append((str(f.relative_to(UPSTREAM)), cid, sent[:120],
                            "cited as %s in a sentence that does not say so" % status))
    assert not bad, bad
    assert "guard-preset-overlap" in statuses, "the row the withdrawal gate depends on is gone"



def test_no_artefact_quotes_a_number_from_the_withdrawn_observation():
    """Mutation: put one of the withdrawn figures -- a range, a recall fraction, an F1 -- into
    `pr-description.md`, and this row reddens before any reader does.

    Spec 7.1 keeps the guardrail anecdote's numbers out of a report, README or PR description until all
    three reproduction conditions are met. Scanning the literals is how a document-only artefact can
    be policed at all; the diff under `patch/` is out of scope here because its fixtures carry the
    author's measured values, and `SUBMISSION.md` says that in prose instead of quoting the numbers.
    """
    hits = []
    for f in prose_artefacts():
        body = f.read_text(encoding="utf-8", errors="ignore")
        for fig in WITHDRAWN_FIGURES:
            if fig in body:
                hits.append((str(f.relative_to(UPSTREAM)), fig))
    assert not hits, "a withdrawn figure was quoted: %s" % hits


def test_the_withdrawn_figure_scan_fires_on_a_plant(tmp_path):
    """Mutation: weaken `WITHDRAWN_FIGURES` or the scan, and the plant below stays clean.

    Same reason as the path plant: the published artefacts are not edited to prove a guard works, so
    the plant is written into a copy of `pr-description.md` and scanned the same way.
    """
    plant = tmp_path / "pr-description.md"
    plant.write_text(text(Path("pr-description.md")), encoding="utf-8")
    clean = [f for f in WITHDRAWN_FIGURES if f in plant.read_text(encoding="utf-8")]
    assert not clean, "the published description already carries %s" % clean
    plant.write_text(plant.read_text(encoding="utf-8") + "\nthe ranges span %s\n"
                     % WITHDRAWN_FIGURES[4], encoding="utf-8")
    assert any(f in plant.read_text(encoding="utf-8") for f in WITHDRAWN_FIGURES), "plant missed"


def test_section_7_1_reproduction_conditions_are_measured_not_assumed():
    """Mutation: point the probes at something that is not there and the row raises instead of
    reporting "unmet".

    Three conditions, each measured here rather than copied from the spec: (a) the patch applies to a
    clean `v0.3.20` checkout, (b) the guard prompts are committed as per-case records, (c) both ranges
    are re-derived by `autorate verify`. The verdict dict is what the next row keys its requirement
    on, so it must never be a guess.
    """
    verdict = measure_section_7_1()
    assert set(verdict) == {"patch_on_clean_checkout", "prompts_committed_as_records",
                            "ranges_rederived_by_verify"}, verdict
    for k, v in verdict.items():
        assert isinstance(v, bool), "%s did not produce a measurement: %r" % (k, v)
    assert LEDGER.exists()


def measure_section_7_1() -> dict:
    """The three conditions of spec 7.1, each as a measurement over this tree.

    (a) is measured by staging a clean copy and running `git apply --check` inside it, exactly as the
    published row does; a source that cannot be found yields `False` rather than a pass, because a
    condition that cannot be demonstrated is a condition that is not met.
    """
    staged, _err = _stage_clean_copy(_scratch_root())
    patch_applies = False
    if staged is not None:
        rc, _out = _apply_check(staged)
        patch_applies = rc == 0
    return {"patch_on_clean_checkout": patch_applies,
            "prompts_committed_as_records": _guardrail_records_present(),
            "ranges_rederived_by_verify": _verify_rederives_ranges()}



def test_the_withdrawal_sentences_are_present_because_a_condition_is_unmet():
    """Mutation: delete either required sentence, or add a hedge from `SOFTENINGS`, in
    `pr-description.md` or `SUBMISSION.md`.

    This is the anti-softening gate. When any condition of spec 7.1 is unmet the artefacts must state
    that the claim stays withdrawn and that the report does not quote it -- and must not reach for the
    phrasings that turn a withdrawal back into a claim by degrees.
    """
    verdict = measure_section_7_1()
    unmet = sorted(k for k, v in verdict.items() if not v)
    assert unmet, "every condition measured as met -- then this row's premise is gone and the " \
                  "sentences below are not a requirement: %s" % verdict
    for rel in ("pr-description.md", "SUBMISSION.md"):
        body = text(Path(rel))
        for sentence in WITHDRAWAL_SENTENCES:
            assert sentence in body, "%s does not say %r while %s is unmet" % (rel, sentence, unmet)
        for name in unmet:
            assert name in body, "%s does not name the unmet condition %r" % (rel, name)
        for hedge in SOFTENINGS:
            assert hedge not in body, "%s softens the withdrawal with %r" % (rel, hedge)


def test_the_patch_applies_to_a_clean_checkout_without_touching_it():
    """Mutation: reword a hunk's context so it no longer matches the tag blobs, and `--check` reddens.

    PF-D-7: `git apply` against the vendored checkout would write into a read-only corpus. So the four
    target files are copied out of a pristine source, `--check` runs inside the copy, and the source's
    digests and mtimes are re-read afterwards to prove the check never wrote back.
    """
    kind, source = _clean_source()
    if kind is None:
        pytest.skip("no pristine v0.3.20 source found; looked at %s" % source)
    src_files = [source / rel for rel in PATCH_TARGETS] if kind == "dir" else []
    before = [_fingerprint(f) for f in src_files]
    staged, err = _stage_clean_copy(_scratch_root())
    assert staged is not None, "could not stage a clean copy of %s (%s): %s" % (kind, source, err)
    for rel in PATCH_TARGETS:
        assert (staged / rel).is_file(), "staged copy is missing %s" % rel
    rc, out = _apply_check(staged)
    assert rc == 0, "git apply --check failed in the scratch copy: rc=%d\n%s" % (rc, out)
    assert "Checking patch" in out or out == "", out
    # A `dir` source is the read-only corpus case; zip and tar are opened through their archives, so
    # there is nothing on disk for the check to have written into.
    after = [_fingerprint(f) for f in src_files]
    assert before == after, "the check wrote into the read-only source tree"


def test_submission_carries_the_do_not_submit_line_and_the_dated_queries():
    """Mutation: drop the approval line, the two-PR order, or the date stamp on a query block.

    Plan D Task 6 stops at text. The line has to name what approval would look like, and the emptiness
    re-check has to be dated, because spec 13's 2026-09-30 result may not be reused: the upstream state
    moves.
    """
    body = text(Path("SUBMISSION.md"))
    assert "DO NOT SUBMIT WITHOUT EXPLICIT HUMAN APPROVAL" in body
    for phrase in ("no issue is opened", "no PR is pushed", "no fork", "not a `git push`"):
        assert phrase in body, "the red lines section omits %r" % phrase
    assert "patch first" in body and "second, separate PR" in body, "the two-PR order is missing"
    stamps = re.findall(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", body)
    assert len(stamps) >= 6, "the query transcript is not dated: %d stamps" % len(stamps)
    assert "UTC" in body, "the timestamps do not say which timezone they are in"
    for label in ("gh api", "git apply --check", "search/issues"):
        assert label in body, "SUBMISSION.md never records %s" % label


def test_the_awesome_jev_entry_is_either_backed_or_omitted_with_its_reason():
    """Mutation: replace the omission record with an entry whose claims name no verified ledger row.

    The plan makes this file conditional: an entry only if the upstream README really lists a
    Jev-compatible ecosystem and every claim in the entry is backed by a `verified` ledger row. Omitting
    is a real option, but it has to be an argument -- so the file must either propose an entry with
    citations, or say `OMITTED` and name the measured premise that failed.
    """
    body = text(Path("awesome-jev-entry.md"))
    omitted = "OMITTED" in body
    if omitted:
        assert "no entry is proposed" in body, "OMITTED without saying what is omitted"
        for reason in ("ecosystem", "ledger"):
            assert reason in body.lower(), "the omission does not address %r" % reason
        assert "2026-10-14" in body, "the omission is not tied to the date it was re-measured"
    else:
        cites = [c for c, _ in citations(UPSTREAM / "awesome-jev-entry.md")]
        statuses = ledger_statuses()
        assert cites, "a proposed entry cites no ledger row"
        assert all(statuses.get(c) == "verified" for c in cites), cites
    # exactly one branch, never both
    assert not (omitted and "- [autorate" in body), "an entry is proposed inside an omission record"


def test_the_pr_description_and_issue_stay_inside_the_two_pr_order():
    """Mutation: merge the audit into the patch PR -- one sentence in `pr-description.md` -- and the
    row that pins the order goes red.

    Spec 13 fixes the order: the self-contained patch first, the confidence-semantics audit and the
    adapter as a second, separate PR. `issue.md` must also keep the withdrawn anecdote out of its own
    argument, which is the same scan as row 5 but named here because the issue is the artefact a
    maintainer reads first.
    """
    pr = text(Path("pr-description.md"))
    issue = text(Path("issue.md"))
    assert "second, separate PR" in pr or "second separate PR" in pr
    assert "does not" in pr and "adapter" in pr, "the patch PR's scope is not stated"
    for hedge in SOFTENINGS:
        assert hedge not in issue, "issue.md softens the withdrawal with %r" % hedge
    assert "v0.3.20" in issue and "v0.3.20" in pr, "the revision under review is not named"
    assert "2026-10-14" in pr, "the PR description does not say when the upstream state was measured"
