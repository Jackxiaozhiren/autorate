"""The repository's instructions for a coding agent are published text, so they are policed like one.

Why a guard and not a hope: `AGENTS.md` exists so that a session handed only the clone can read the rules this
project has bled over, and a file that states a rule the gate does not enforce -- or cites a test that does not
exist -- is worse than no file, because it converts a guess into a citation. So the rows below check three
things that can actually go wrong: the exit codes the file names are the ones the CLI publishes (read from
`cli`, never retyped), every test the file cites exists, and every rule subject the plans treat as binding is
mentioned by name.
"""
import pathlib
import re

import pytest
from autorate import cli

REPO = pathlib.Path(cli.__file__).resolve().parents[2]
INSTRUCTIONS = REPO / "AGENTS.md"

# The rules a clone cannot infer from the code, each named by the subject a reader would grep for.
RULE_SUBJECTS = (
    "exit code",
    "read-only",
    "absolute",
    "noqa",
    "uv run --frozen",
    "python3",
    "R-41",
    "commit message",
    "case",
)


def _text() -> str:
    return INSTRUCTIONS.read_text(encoding="utf-8")


def test_the_repository_ships_agent_instructions_at_the_root():
    assert INSTRUCTIONS.is_file(), (
        "a session handed this clone alone cannot read the project's constraints: no `AGENTS.md` at the root, "
        "and the rules live only in `docs/superpowers/plans/*.md`, which nothing points a reader toward")


def test_the_instructions_name_every_published_exit_code_with_the_number_the_cli_publishes():
    """The codes are read out of `cli`, so the document cannot drift from the contract it describes."""
    text = _text()
    published = {"certified": cli.EXIT_CERTIFIED, "usage": cli.EXIT_USAGE,
                 "not-certifiable": cli.EXIT_NOT_CERTIFIABLE, "drift": cli.EXIT_DRIFT}
    assert len(set(published.values())) == 4, published
    for name, code in published.items():
        assert re.search(r"\b%s\b" % re.escape(name), text, re.I), (
            "`AGENTS.md` never names the %s exit code" % name)
        assert "`%d`" % code in text, (
            "the %s code's number %d is not stated in `AGENTS.md` -- a rule that says 'exit codes matter' "
            "without the digits is not actionable" % (name, code))


def _cited_guards(text: str) -> set:
    """The guard names the file cites, read out of backticked spans only.

    A first version searched the whole document with `\\btest_\\w+\\b` and reported `test_cli` and
    `test_verify_protocol` as missing guards -- those are the FILE names inside `tests/test_cli.py::test_...`.
    So a citation is taken from a backtick span, and inside one, after the `::` that separates a module from a
    test; a span containing a slash without a `::` names a file, which is a different claim to check.
    """
    cited = set()
    for span in re.findall(r"`([^`]+)`", text):
        span = span.strip()
        if "::" in span:
            tail = span.split("::")[-1].strip()
            if re.fullmatch(r"test_[a-z0-9_]+", tail):
                cited.add(tail)
            continue
        if "/" in span or span.endswith(".py"):
            continue
        if re.fullmatch(r"test_[a-z0-9_]+", span):
            cited.add(span)
    return cited


def test_every_test_the_instructions_cite_exists_in_the_suite():
    """A citation to a guard that is not there is how a document starts lying about what is enforced."""
    cited = _cited_guards(_text())
    assert cited, "the file cites no guard rows at all, so this row has nothing to check"
    suite = " ".join(path.read_text(encoding="utf-8") for path in (REPO / "tests").glob("*.py"))
    missing = sorted(name for name in cited if ("def %s(" % name) not in suite)
    assert not missing, "`AGENTS.md` cites guards that do not exist: %s" % missing


def test_the_cited_guard_names_are_parsed_not_guessed():
    """The extractor is policed too: a citation grammar that silently matches nothing passes vacuously.

    The planted cases are the two shapes the document actually uses -- a bare `test_x` and a
    `tests/test_file.py::test_x` -- and the false-positive shape is the file name on its own, which the first
    version of this row reported as a missing guard.
    """
    sample = ("see `test_alpha_row` and `tests/test_cli.py::test_beta_row` and the module "
              "`tests/test_cli.py` and `test_gamma_row`")
    assert _cited_guards(sample) == {"test_alpha_row", "test_beta_row", "test_gamma_row"}, _cited_guards(sample)
    real = _cited_guards(_text())
    assert len(real) >= 5, "only %d citations parsed from AGENTS.md -- the grammar or the file regressed" % len(real)


@pytest.mark.parametrize("subject", RULE_SUBJECTS)
def test_the_instructions_state_each_binding_rule_by_its_own_subject(subject):
    """Dropping a rule from the file has to be visible, not silent.

    Parametrised over a declared list rather than a single regex over the whole file: a row that asserted "the
    file mentions constraints" would pass on a file that had dropped the read-only corpus or the pre-push
    simulation entirely, which are the two rules whose absence costs the most.
    """
    assert re.search(re.escape(subject), _text(), re.I), (
        "`AGENTS.md` no longer states the %r rule" % subject)


def test_the_instructions_carry_no_absolute_machine_path():
    text = _text()
    offenders = sorted({m.group(0) for m in re.finditer(r"/Users/[A-Za-z0-9._-]+", text)})
    assert not offenders, "the instruction file itself carries a home path: %s" % offenders


def test_the_instructions_point_at_where_the_rulings_live():
    text = _text()
    for target in (".superpowers/sdd", "docs/ERRATA.md", "docs/VERIFICATION.md"):
        assert target in text, "`AGENTS.md` never points a reader at %s" % target
