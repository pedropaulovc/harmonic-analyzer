"""Temporary one-view native Title-link discovery, not the full fit proof.

The executable source fixes the observational mode so its file dependency is
part of the cache identity. Do not express this mode as argv to the full
probe: COM cache keys contain file dependencies, not command arguments.
Remove this executable and its task after native positive/full proof.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import run_build  # noqa: E402
from diagnostics.probe_title_field_fit import probe  # noqa: E402


if __name__ == "__main__":
    sys.exit(run_build(lambda adapter: probe(adapter, legacy_only=True)))
