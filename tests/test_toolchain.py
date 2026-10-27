"""The toolchain contract: one interpreter, frozen lock, no bare python."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_version_has_one_owner():
    import tomllib

    import autorate

    declared = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert autorate.__version__ == declared, (autorate.__version__, declared)
    assert autorate.__version__.count(".") == 2


def _interpreter_versions(pyproject_text, pinned_text, ci_text, running_text):
    """The four places this project states which interpreter it runs on, as (source, version) pairs.

    A helper over texts rather than over files so the row below can be shown able to fail: the whole point is
    that four documents agree, and an agreement checked only against the current bytes proves nothing about a
    future disagreement.
    """
    import re

    floor = re.search(r'requires-python = ">=([0-9]+\.[0-9]+)"', pyproject_text)
    pinned = re.search(r"^(3\.[0-9]+)\s*$", pinned_text, re.M)
    ci = re.findall(r'python-version: "?([0-9]+\.[0-9]+)"?', ci_text)
    running = re.match(r"(3\.[0-9]+)", running_text.strip())
    found = []
    if floor:
        found.append(("pyproject `requires-python` floor", floor.group(1)))
    if pinned:
        found.append(("`.python-version`", pinned.group(1)))
    for index, version in enumerate(ci):
        found.append(("ci.yml python-version #%d" % index, version))
    if running:
        found.append(("the interpreter running this suite", running.group(1)))
    return found


def test_the_declared_python_floor_is_the_interpreter_the_gate_actually_runs():
    r"""`requires-python` is a published promise, so it cannot name a version nothing has executed.

    Why this row exists, measured rather than argued. A clean `git archive` export was synced with
    `uv sync --frozen` and ran `autorate verify` on Python 3.10.20 and on 3.11.15. Both installed cleanly, and
    both refused: rc=4, `re-derived 890 /895 values`, with exactly five `DRIFT: cert massive/<lang>.meta` lines
    whose difference is the last place of a `diagnostic_curve` `qhat` (``...7806`` against ``...7807``). That is
    not a bug in the comparison -- the whole `meta` block is compared precisely because a stored meta is a claim
    about the run -- so an interpreter whose libm rounds differently genuinely cannot reproduce the published
    artefact, and `>=3.10` was a false statement in the package metadata. The floor is now the version
    `.python-version`, `ci.yml` and the export all run.

    What the row refuses: any one of the four statements moving away from the others. That is the failure mode
    this repository keeps recording -- four documents that each restate one fact and drift one at a time -- and
    `test_the_floor_row_can_fail_for_each_source` forges it rather than asserting it.
    """
    found = _interpreter_versions(
        (ROOT / "pyproject.toml").read_text(),
        (ROOT / ".python-version").read_text(),
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(),
        sys.version,
    )
    assert len(found) >= 4, found
    versions = {version for _source, version in found}
    assert versions == {"3.12"}, "the interpreter is stated %d times and they disagree: %s" % (
        len(found), sorted(found))


def test_the_floor_row_can_fail_for_each_source():
    """Forge each of the four statements and require the row to name the one that moved."""
    pyproject = (ROOT / "pyproject.toml").read_text()
    pinned = (ROOT / ".python-version").read_text()
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    baseline = {version for _s, version in _interpreter_versions(pyproject, pinned, ci, sys.version)}
    assert baseline == {"3.12"}, baseline
    for label, forged in (
            ("pyproject", pyproject.replace('>=3.12', '>=3.10')),
            (".python-version", pinned.replace("3.12", "3.11")),
            ("ci.yml", ci.replace('python-version: "3.12"', 'python-version: "3.13"')),
            ("interpreter", "3.14.0 (main)")):
        moved = _interpreter_versions(pyproject, pinned, ci, sys.version)
        if label == "pyproject":
            moved = _interpreter_versions(forged, pinned, ci, sys.version)
        elif label == ".python-version":
            moved = _interpreter_versions(pyproject, forged, ci, sys.version)
        elif label == "ci.yml":
            moved = _interpreter_versions(pyproject, pinned, forged, sys.version)
        else:
            moved = _interpreter_versions(pyproject, pinned, ci, forged)
        assert {version for _s, version in moved} != {"3.12"}, (
            "forging %s did not create a disagreement, so that source is not actually policed: %s" % (
                label, sorted(moved)))


def test_tests_run_on_the_project_interpreter_not_the_path_one():
    # Guards Global Constraint 5: `which pytest` on this host is a Python 3.9 binary.
    assert sys.version_info[:2] == (3, 12), (
        f"expected the pinned 3.12 dev env, got {sys.version.split()[0]} from {sys.executable}"
    )


def test_lock_is_committed_and_up_to_date_with_pyproject():
    # Guards Global Constraint 7's artefact: uv.lock is committed, and `uv lock --check` fails when
    # pyproject.toml drifts from it. A plain interpreter run cannot re-lock, so a byte-compare around
    # `python -c "import autorate"` could never fail; the lock check is the guard that can.
    assert (ROOT / "uv.lock").exists()
    proc = subprocess.run(
        ["uv", "lock", "--check"], capture_output=True, text=True, cwd=ROOT
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def _ci_lint_command() -> list:
    """Read the gate's own command out of ci.yml rather than restating it here.

    Two literals for one gate is how a lint rule list drifts: this test would stay green
    while the runner stopped checking the same things.
    """
    import re

    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    line = [l for l in text.splitlines() if "ruff check" in l]
    assert len(line) == 1, line
    step = line[0].strip().lstrip("-").strip()
    assert step.startswith("run:"), step
    command = step.split("run:", 1)[1].split("|")[0]
    return [tok.strip("\"'") for tok in re.findall(r"[^\s]+", command)]


def test_ruff_gate_matches_the_upstream_shape():
    cmd = _ci_lint_command()
    assert cmd[:4] == ["uv", "run", "--frozen", "ruff"], cmd
    proc = subprocess.run([sys.executable, "-m", *cmd[3:]],
                          capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert any(tok.startswith("--select=") for tok in cmd), cmd
    assert any(tok.startswith("--line-length=") for tok in cmd), cmd


def test_declared_console_script_entry_point_resolves_and_runs():
    """R-6: resolve the declared target, then run it as a subprocess -- never in-process.

    Neither ruff nor compileall resolves `autorate = "autorate.cli:main"`, so without this
    a rename or deletion of `main` stays green. Calling `scripts[0].load()()` in-process
    did resolve it, but Task 9's `main(argv=None)` reads pytest's own `sys.argv`, so the
    only honest entry-point check is the one that runs the installed script and reads its
    exit code -- the same contract a shell user gets.
    """
    from importlib.metadata import entry_points

    scripts = [ep for ep in entry_points(group="console_scripts") if ep.name == "autorate"]
    assert len(scripts) == 1, f"expected one `autorate` console script, got {scripts}"
    assert scripts[0].value == "autorate.cli:main", scripts[0].value
    script = Path(sys.executable).parent / "autorate"
    assert script.exists(), "the declared console script is not installed"
    proc = subprocess.run([str(script), "--help"], capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "verify" in proc.stdout, proc.stdout
