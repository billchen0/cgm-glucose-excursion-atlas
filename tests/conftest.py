"""Test configuration.

Puts the repository root on `sys.path` so `tests.fixtures` is importable regardless of
how pytest was invoked, and so `cgm_excursions` resolves from `src/` without requiring
an editable install.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
