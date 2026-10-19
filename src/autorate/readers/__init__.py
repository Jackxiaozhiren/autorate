"""The reader package's public surface.

`read_archive` is the corpus entry point and `records_from_line` the per-line parser; both are
named in `__all__` so a linter reads them as re-exported rather than unused -- the alternative was an inline
waiver, which AGENTS.md rule 11 forbids.
"""
from .feishu_zh import read_archive, records_from_line

__all__ = ["read_archive", "records_from_line"]
