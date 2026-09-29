r"""McMaster 93075A150 -- low-strength zinc-plated steel hex head screw, #6-32 x 5/8".

Catalogue: the McMaster product page https://www.mcmaster.com/93075A150/
(read through Browserbase on 2026-09-25 for the I31 hold-down; the tip
block's foot flange is sized for it in ``cone_tip_block_spec``): #6-32 UNC,
5/8 in (15.875) under the head, fully threaded, zinc-plated low-strength
steel, ASME B18.6.3; hex head 1/4 in across flats (0.244 min) and 3/32 in
high (0.080 to 0.093), across corners 0.272 min.  The replica takes the
1/4 across flats, the #6 major, 0.138 in (3.5052), and the head at its
0.093 in (2.3622) maximum height, the vendor model's ``Head Height``
(harvested 2026-09-29; the nominal 3/32 in is 0.019 mm taller).

Geometry: the 93075A* family laws of ``diag_mcmaster_hex_head.py`` -- the
laws ``diag_build_93075A194.py`` reads off the vendor 93075A194 model and
proves against it in the replica gate -- at those five catalogue dimensions.
The vendor model (downloaded 2026-09-29, local-only at
``cad/references/mcmaster/93075A150.SLDPRT``, gitignored) is harvested
read-only by ``diag_dump_part.py`` and this size is replica-gated against it
(``diag_build_mcmaster.py 93075A150``): volume, area, face multiset and
centre of mass.  ``test_cone_tip_block_screw_drawing.py`` pins the catalogue
dimensions and proves the family builder reproduces 93075A194's recipe call
for call.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_93075A150.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_hex_head import (  # noqa: E402
    HexHeadScrew,
    build_hex_head_screw,
)

PART_NO = "93075A150"
IN = 25.4
DIMS = HexHeadScrew(
    part_no=PART_NO,
    major_dia=0.138 * IN,
    pitch=IN / 32.0,
    length=0.625 * IN,
    head_af=0.25 * IN,
    head_h=0.093 * IN,
)


async def build_93075A150(adapter, truth=None):
    await build_hex_head_screw(adapter, DIMS)


if __name__ == "__main__":
    from diagnostics.diag_mcmaster_lib import replica_main

    sys.exit(replica_main(PART_NO, build_93075A150))
