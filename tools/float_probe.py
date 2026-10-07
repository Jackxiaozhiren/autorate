"""Print the platform and the float evidence a reproducibility claim is actually made of.

    uv run --frozen python3 tools/float_probe.py

Why this file exists (ledger R-121). `autorate verify` re-derives every published number and
compares it with `==`. That is an honest gate only when a committed number is one any C library
reproduces bit for bit, and the last bits of `math.log` and `math.exp` are not the same between
Apple libm and glibc: at `351845e` the runner recomputed a Clopper-Pearson bound as
`0.7884344428029711` where the artefact said `0.7884344428029715`, and two CI runs were red while
the machine that wrote the file stayed green. Both runs printed the same conclusion -- `DRIFT` --
and neither printed anything that could tell "the artefact is wrong" from "this is a different
machine", because `pytest -q` suppressed the header and no step printed the math library at all.

This step is that missing evidence, and it separates the two hypotheses in one line:

* same commit + same probe bits + a mismatched artefact => the artefact or the code is wrong;
* same commit + different probe bits => the platform's math library differs.

The probes are fixed inputs, never measured data, so two runs are comparable without knowing what
the corpus was. Each answer is printed as the shortest string that round-trips (`repr`, which
Python guarantees re-reads to the identical double) and as the exact hexadecimal expansion of the
double, so a difference in the last bit is visible without reading a dict repr, and the `sha256`
over the shortest reps collapses a whole run to one token a reader can diff.

Nothing here is a gate on its own: it prints, it does not judge, and it decides nothing about the
code under test. It exits 0, or 4 (`EXIT_DRIFT`, the repository's "our arithmetic did not
reproduce" family) if a probe cannot be computed -- a disclosure step that failed quietly would be
the worst possible outcome, since the entire point of it is the disclosure. Exit 1 is unreachable:
every path returns a documented code, and an unexpected exception is reported rather than allowed
to leave a traceback behind.

Stdlib plus this project's own `tails` and `certificate`, so no new dependency and no network.
"""
from __future__ import annotations

import hashlib
import importlib.util
import math
import platform
import sys
import sysconfig
from typing import Optional, Sequence


def _clopper(k: int, n: int, delta: float) -> float:
    from autorate.tails import clopper_pearson_upper

    return clopper_pearson_upper(k, n, delta)


def _width(n: int, alpha: float) -> float:
    from autorate.tails import bound_width

    return bound_width(n, alpha)


def _canon(value: float) -> float:
    from autorate.certificate import canonicalise_bound

    return canonicalise_bound(value)


# The probe set. Fixed inputs chosen for one property each, and named by the expression so a
# reader can paste it. `math.exp(-1.3)` is the bare libm call the bisection is built from, and it
# needs no project import at all -- the control that says "this is the C library, not our code".
# `clopper_pearson_upper(21, 33, 0.05)` is a published bound of the same family the R-121 incident
# was: the same 33-case denominator, the same delta, the same inversion. `bound_width(2974, 0.05)`
# is the DKW half-width behind every `autorate_ci`, on the 2,974-case corpus the certificate
# denominators are quoted at. And the fourth probe is the fix itself: the ceiling
# `canonicalise_bound` puts on the exact double the two libms disagreed over, so a run can be read
# against the published number rather than against a private computation.
PROBES = (
    ("math.exp(-1.3)", lambda: math.exp(-1.3)),
    ("clopper_pearson_upper(21, 33, 0.05)", lambda: _clopper(21, 33, 0.05)),
    ("bound_width(2974, 0.05)", lambda: _width(2974, 0.05)),
    ("canonicalise_bound(0.7884344428029715)", lambda: _canon(0.7884344428029715)),
)

EXIT_OK = 0
EXIT_DRIFT = 4


def platform_lines() -> list:
    """Who is running this, in the words the platform module gives -- no judgement, no gate.

    `platform.libc_ver()` is the line the R-121 diagnosis wanted and did not have. It names the C
    library on glibc systems and returns a pair of empty strings on darwin, where the
    transcendentals live in libSystem rather than in a libc a probe can identify -- so the empty
    pair is printed AS evidence, with that reading beside it, rather than looking like a missing
    reading. `MULTIARCH` is the same distinction from the interpreter's own build record.
    """
    libc = platform.libc_ver()
    lines = [
        "platform: %s %s (%s)" % (platform.system(), platform.release(), platform.machine()),
        "python: %s (%s)" % (sys.version.split()[0], sys.executable),
        "libc_ver: %r" % (libc,),
    ]
    if not any(libc):
        lines.append("libc_ver: no name reported -- on darwin the transcendentals come from "
                     "libSystem, not from a glibc a probe can identify; an empty pair here is the "
                     "Apple-libm arm, not a missing reading")
    else:
        lines.append("libc_ver: the glibc arm; two runs differing here are different math "
                     "libraries, which is the hypothesis `verify`'s exact `==` cannot separate "
                     "on its own")
    lines.append("sysconfig: platform=%r, multiarch=%r" % (
        sysconfig.get_platform(), sysconfig.get_config_var("MULTIARCH")))
    lines.append("sysconfig: purelib=%r" % (sysconfig.get_path("purelib"),))
    return lines


def probe_lines() -> list:
    """The fixed transcendental answers, as shortest-repr doubles and as exact hex."""
    lines = ["float probe (shortest repr that round-trips, plus the exact hex of the double):"]
    digest = hashlib.sha256()
    for name, call in PROBES:
        value: float = call()
        text = repr(value)
        lines.append("  %-38s = %s  hex=%s" % (name, text, float(value).hex()))
        digest.update(("%s=%s\n" % (name, text)).encode("utf-8"))
    lines.append("  probe digest (sha256 over the shortest reps, first 16 hex): %s"
                 % digest.hexdigest()[:16])
    return lines


def random_order_lines() -> list:
    """Say which is true about test ordering, by asking rather than by repeating a claim.

    The command card in `.superpowers/sdd/export-lane-commands.md` passes `-p no:randomly`, which
    reads as though this project shuffled test order and had switched it off. Measured, it does
    not: `pytest-randomly` is not a dependency, so the flag blocks a plugin that was never going to
    load and the order is pytest's own deterministic file/definition order. That distinction is
    what a CI-only failure turns on -- with a fixed order a red cannot be an ordering artefact --
    so it is probed on every run instead of asserted once in prose.
    """
    installed = importlib.util.find_spec("pytest_randomly") is not None
    if installed:
        return ["test order: pytest-randomly IS installed, so pytest's own header -- no longer "
                "suppressed in CI -- names the plugin and its summary prints `seed: N`; record it "
                "and a CI-only failure is replayable verbatim with --randomly-seed=N"]
    return ["test order: pytest-randomly is NOT a dependency of this project (absent from uv.lock "
            "and from the synced venv), so `-p no:randomly` is a no-op and collection order is "
            "deterministic file/definition order -- there is no seed to record, and a CI-only "
            "failure cannot be an ordering artefact"]


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Print the whole disclosure, and exit 0, or 4 if a probe could not be computed."""
    del argv                                        # no operator-tunable surface, by design
    try:
        lines = platform_lines() + probe_lines() + random_order_lines()
    except Exception as exc:
        print("float-probe INCOMPLETE: %s: %s -- this run carries no platform evidence, which is "
              "the condition R-121 was diagnosed in" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_DRIFT
    for line in lines:
        print(line)
    print("float-probe: complete")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
