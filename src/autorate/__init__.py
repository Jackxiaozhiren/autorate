from importlib.metadata import version as _dist_version

# pyproject.toml owns the version; a second literal here goes stale the first time one is
# bumped and nothing in the suite could notice.
__version__ = _dist_version("autorate")

from .certificate import Certificate, Reason
from .certify_choice import certify_choice
from .gate import Gate
from .records import (
    NOUL_SLOTS,
    QTYPES,
    Record,
    entropy_confidence,
    is_hashable_key,
    max_confidence,
    validate,
)

__all__ = [
    "__version__",
    "Certificate",
    "Reason",
    "Gate",
    "certify_choice",
    "QTYPES",
    "NOUL_SLOTS",
    "Record",
    "validate",
    "max_confidence",
    "entropy_confidence",
    "is_hashable_key",
]
