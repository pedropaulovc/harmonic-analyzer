r"""MSC 40923898 -- 1/4-20 x 3-1/2 zinc-plated steel slotted fillister screw.

MSC Industrial Supply, manufacturer part 1456MSL (SAE J82 steel, zinc,
ASME B18.6.3, fully threaded).  MSC publishes no head sizes and no CAD
model, so the head takes ASME B18.6.3's 1/4 maximum and the length the
86.0 cut-to-fit nominal (U37c).  Reuses the 90280A* fillister family laws
unchanged, like 90280A837.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_40923898.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402


async def build_40923898(adapter, truth=None):
    await build_fillister(adapter, "40923898")


if __name__ == "__main__":
    sys.exit(replica_main("40923898", build_40923898))
