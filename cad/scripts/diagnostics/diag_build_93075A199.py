r"""McMaster 93075A199 -- low-strength zinc-plated steel hex head screw, #8-32 x 1".

Used as pn-vn-hanger-screw (MHA-PN-VN-50): from behind the wheel bar through the
pen-hanger strap's clearance hole into the MHA-PN-VN-54 nut and MHA-PN-VN-55 jam nut.
The catalogue facts are ``_mcmaster_93075a199``'s.  Geometry: the 93075A*
family laws of ``diag_mcmaster_hex_head.py`` at this size's five catalogue
dimensions.  Those laws were read off the vendor 93075A194 model, whose
recipe and replica gate #2896 deleted; they are frozen and catalogue-only
(owner ruling 2026-11-20, #2926).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_93075A199.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_93075a199 import (  # noqa: E402
    HX_HH,
    HX_HW,
    HX_LEN,
    HX_MAJOR_R,
    HX_PITCH,
)
from diagnostics.diag_mcmaster_hex_head import (  # noqa: E402
    HexHeadScrew,
    build_hex_head_screw,
)
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402

DIMS = HexHeadScrew(
    part_no="93075A199",
    major_dia=2.0 * HX_MAJOR_R,
    pitch=HX_PITCH,
    length=HX_LEN,
    head_af=HX_HW,
    head_h=HX_HH,
)


@stock_recipe("93075A199", threaded=True)
def build_93075A199(adapter, truth=None):
    build_hex_head_screw(adapter, DIMS)


if __name__ == "__main__":
    sys.exit(replica_main("93075A199", build_93075A199))
