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


def test_lock_is_committed_and_frozen_run_does_not_rewrite_it():
    assert (ROOT / "uv.lock").exists()
    before = (ROOT / "uv.lock").read_bytes()
    subprocess.run(
        [sys.executable, "-c", "import autorate"], check=True, cwd=ROOT
    )
    assert (ROOT / "uv.lock").read_bytes() == before, "plain run re-locked the tree"


def test_ruff_gate_matches_the_upstream_shape():
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "src", "tests",
         "--select=E9,F63,F7,F82,F401,F811", "--line-length=120"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
