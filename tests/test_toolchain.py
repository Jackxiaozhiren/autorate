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
