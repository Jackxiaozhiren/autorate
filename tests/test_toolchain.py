"""The toolchain contract: one interpreter, frozen lock, no bare python."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_imports_and_declares_version():
    import autorate

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


def test_ruff_gate_matches_the_upstream_shape():
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "src", "tests",
         "--select=E9,F63,F7,F82,F401,F811", "--line-length=120"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


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
