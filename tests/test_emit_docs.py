"""`autorate emit-docs`: the one write surface a freeze round needs, derived from `cli.PUBLISHED_DOCS`.

Task #99's complaint was never "a stale document can slip through" -- `verify` re-renders every row of the table
and byte-compares, so a forgotten document is exit 4. What was missing is that no command in the repository
answers "how do I regenerate this document", so each round re-rendered from a script kept OUTSIDE the repo (a
loop over `cli.PUBLISHED_DOCS`, `t99/emit_docs.py`) that a reader of the published tree cannot find, run, or
fix. A published v1 whose regeneration procedure lives in someone's scratch directory is not reproducible from
the commit, which is the criterion G5 is built on.

The table is the only list. These rows therefore police the writer against the table itself, in both directions:
the set it writes must equal the set the table declares, and an operator cannot aim it at a path the table does
not declare. The two refusal rows are what make the first one mean something -- a writer that skipped a document
it could not render would still have "written everything it wrote".
"""
import pathlib

import pytest

from autorate import cli

REPO = pathlib.Path(cli.__file__).resolve().parents[2]


def _published_paths():
    return {str(path) for path, _render in cli.PUBLISHED_DOCS}


@pytest.fixture
def in_repo(monkeypatch):
    monkeypatch.chdir(REPO)


def test_emit_docs_writes_every_document_the_table_declares_and_no_others(in_repo, tmp_path, capsys):
    """The default run is the whole table, byte-identical to what the repository publishes.

    Plant: delete a row from the table and this assertion stops being satisfiable -- the written set no longer
    equals the declared set -- so the row cannot be satisfied by a writer that hard-codes a list.
    """
    rc = cli.main(["emit-docs", "--out-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0, (rc, out)
    written = {str(pathlib.Path(rel).relative_to(tmp_path)) for rel in tmp_path.rglob("*")
               if rel.is_file()}
    assert written == _published_paths(), (
        "`emit-docs` wrote %s while `cli.PUBLISHED_DOCS` declares %s -- the writer and the gate's byte "
        "comparison have to read the same list" % (sorted(written), sorted(_published_paths())))
    for rel in _published_paths():
        produced = (tmp_path / rel).read_bytes()
        committed = (pathlib.Path.cwd() / rel).read_bytes()
        assert produced == committed, "%s: the shipped writer does not reproduce the published bytes" % rel
    assert "documents written: %d" % len(cli.PUBLISHED_DOCS) in out, out


def test_a_document_the_writer_cannot_render_is_a_refusal_not_a_silent_short_run(in_repo, tmp_path, capsys,
                                                                                monkeypatch):
    """One row whose renderer raises has to end the run at 4 naming that document.

    This is the failure mode the round-17 review can reach: a table row reads a published artefact, and an
    artefact that is not there raises `PublishedArtefactUnavailable`. Writing seven of eight documents and
    exiting 0 would leave the freeze looking complete, so the count is checked before the exit code.
    """
    good = list(cli.PUBLISHED_DOCS)
    broken = [(good[0][0], good[0][1]),
              (good[1][0], lambda inv, records: (_ for _ in ()).throw(
                  cli.PublishedArtefactUnavailable("%s is declared published by the table" % str(good[1][0]))))]
    monkeypatch.setattr(cli, "PUBLISHED_DOCS", broken)
    rc = cli.main(["emit-docs", "--out-dir", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == cli.EXIT_DRIFT, (rc, err)
    assert str(good[1][0]) in err, "the refusal does not name the document it could not write: %s" % err
    assert not (tmp_path / str(good[1][0])).exists(), (
        "the writer wrote the documents before the failure and exited non-zero; a partial tree with a loud "
        "message is still a partial tree")


def test_a_path_the_table_does_not_declare_is_a_usage_error(in_repo, tmp_path, capsys):
    """`--only` exists so an operator can retarget one document; it must not become a way to publish a new one.

    Plant: ask for a path outside the table and the run is EXIT_USAGE -- the operator named something the
    publication tables do not, which is a mistake they can correct, per R-272.
    """
    rc = cli.main(["emit-docs", "--out-dir", str(tmp_path), "--only", "docs/NOT_PUBLISHED.md"])
    err = capsys.readouterr().err
    assert rc == cli.EXIT_USAGE, (rc, err)
    assert "docs/NOT_PUBLISHED.md" in err, "the refusal does not echo the path the operator typed: %s" % err
    assert not (tmp_path / "docs/NOT_PUBLISHED.md").exists(), "it refused by writing anyway"


def test_a_declared_path_that_escapes_the_root_is_refused(in_repo, tmp_path, monkeypatch, capsys):
    """The table is trusted, but a row that resolves outside the destination is a defect, not a feature.

    Plant: declare `../escape.md`. The writer must refuse at EXIT_DRIFT (the table declared it, the operator
    typed nothing) and must not create the file.
    """
    row = (pathlib.Path("../escape.md"), lambda inv, records: "planted\n")
    monkeypatch.setattr(cli, "PUBLISHED_DOCS", [row])
    rc = cli.main(["emit-docs", "--out-dir", str(tmp_path)])
    err = capsys.readouterr().err
    assert rc == cli.EXIT_DRIFT, (rc, err)
    assert "escape.md" in err, "the refusal does not name the path it would have escaped through: %s" % err
    assert not (tmp_path.parent / "escape.md").exists(), "it refused by writing outside the destination"
