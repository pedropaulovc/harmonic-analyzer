"""Resolve shared CAD helpers for standalone archived diagnostics.

Path setup only, with no CAD helper re-exports. Kept tracked because resolution
selects the implementation a diagnostic uses.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
