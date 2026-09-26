r"""McMaster 92240A540 -- 18-8 stainless hex head screw, 1/4"-20 x 3/4".

The specified rocker-support hold-down after the 2026-09-25 machinist review:
its 19.05-mm under-head length engages the base 1.956D where 92240A539's 5/8
engages 1.456D. McMaster's page (checked 2026-09-25) lists every field of
92240A539 but the length: 1/4"-20 UNC-2A, fully threaded, 7/16" x 5/32" head,
flat tip, ASME B18.2.1. So this replay is the 92240A539 family law
(``diag_build_92240A539.build_hex_screw``) at 19.05 mm.

Its supplied SolidWorks model (``cad/references/mcmaster/92240A540.SLDPRT``,
SHA-256 0257bc44e4273a32536e58829d52ec552e04b631a472ae080a067f29b38eac39,
see cad/references/mcmaster/README.md) was harvested read-only. Vendor truth:
volume 901.5330 mm^3, area 929.1943 mm^2, 22 faces; ``replica_main`` below
matched all three and the face-area multiset on 2026-09-26. This is the SKU
``build_lag_screw`` builds.

Run standalone (SolidWorks open, harvested SLDPRT in cad/references/mcmaster)::

    uv run python cad\scripts\diagnostics\diag_build_92240A540.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_build_92240A539 import (  # noqa: E402
    HEX_HEIGHT_MM,
    HEX_WIDTH_MM,
    MAJOR_DIAMETER_MM,
    PITCH_MM,
    WASHER_DEPTH_MM,
    build_hex_screw,
)
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402

LENGTH_MM = 19.05
__all__ = (
    "HEX_HEIGHT_MM",
    "HEX_WIDTH_MM",
    "LENGTH_MM",
    "MAJOR_DIAMETER_MM",
    "PITCH_MM",
    "WASHER_DEPTH_MM",
    "build_92240A540",
)


async def build_92240A540(adapter, truth=None):
    """Build 92240A540 by the 92240A539 family law at its 3/4-in length."""
    await build_hex_screw(adapter, sku="92240A540", length_mm=LENGTH_MM)


if __name__ == "__main__":
    sys.exit(replica_main("92240A540", build_92240A540))
