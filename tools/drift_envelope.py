#!/usr/bin/env python3
"""B3's drift envelope, published: the CLI a reader runs for the artefact `autorate verify` re-derives.

    uv run --frozen python3 tools/drift_envelope.py --out data/drift_envelope.json \\
        --doc docs/DRIFT.md --force

This file is a thin entry point and owns no logic. The measurement drivers, the builder, the renderer and the
gate checks live in `src/autorate/drift_envelope.py`, because `autorate verify` has to import them and a
package cannot import a script. That is the fix for MAJOR-1's root cause (`drift-review.md` §7): a tool that
owned builder, renderer and gate logic outside `src/` left the published envelope with no library entry point
for the gate to call, so the artefact was published evidence policed only by pytest.

The shape is the one `tools/g1_feasibility.py` has over `report.build_g1_feasibility`. The full contract — the
three rules that shape the artefact, and the exit-code paragraph (0/2/3/4, nothing escapes at 1) — is the
module's docstring, in `src/autorate/drift_envelope.py`, beside the code that honours it. The artefact's own
`producer` field still names THIS path, because this is the command a reader runs to rewrite the published
bytes, and `docs/DRIFT.md` prints that command in its header.

`tests/test_drift_envelope.py::test_the_drift_logic_lives_in_the_package_and_the_tool_is_a_thin_cli_over_it`
polices this file's thinness by parsing the definitions in its source, so the logic cannot creep back.
"""
from __future__ import annotations

import sys

from autorate.drift_envelope import main

if __name__ == "__main__":
    sys.exit(main())
