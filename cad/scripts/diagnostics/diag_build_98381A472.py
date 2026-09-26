r"""McMaster 98381A472 -- black-oxide alloy steel dowel pin, 1/8" x 5/8" (MHA-152).

The cone tip block's locating dowel (#917 R5): pressed into the swing
platform (MHA-091) from below and a slip fit in the tip block's blind ream,
so the block's fit-up position is recovered after a strip-down.  Main chose
5/8 over 1/2 because the shorter pin ran short at the maximum shim stack.

The section is the supplied vendor file's own, read offline from the
Parasolid partition of ``cad/references/mcmaster/98381A472.SLDPRT`` (SHA-256
45c5290c2bb6fbb47ca3e37465929617aef9c1ada2f40003b66b4d0cebd9adf2, local-only,
never tracked).  It is the 98381A472 (MHA-151) section at 5/8 in length: a
3.175-mm (nominal 1/8") cylinder 15.875 mm long on the model Z axis, centred
on the origin; at -Z a 16-deg-half-angle lead-in cone from the flank to a
1.4605-mm-radius end face (starting at z -7.494598); at +Z an R0.4064 (.016")
toroidal crown blend tangent to the flank and to a 1.1811-mm-radius end face
(centre z 7.5311).  Five faces.  The model carries the nominal diameter, not
the catalog's ground size.

Not yet gated: ``diag_dump_part.py`` has not harvested the file and
``replica_main`` below has not run on a seat.  The replay revolves the section
about model Y, like the rest of the stock fleet (``ScrewAxis`` = Front x
Right), and maps its centre of mass into the vendor's Z-axis frame for the
gate.

Run standalone (SolidWorks open, harvested SLDPRT in cad/references/mcmaster)::

    uv run python cad\scripts\diagnostics\diag_build_98381A472.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import add_line_chain, check, name_last_feature, volume_check  # noqa: E402
from diagnostics.diag_mcmaster_lib import no_sketch_inference, replica_main  # noqa: E402

MM_PER_IN = 25.4
PIN_RADIUS = 0.125 * MM_PER_IN / 2.0
PIN_LENGTH = 0.625 * MM_PER_IN
# The section spans model Y symmetrically, so the part's Top Plane (y = 0) is
# the pin's mid-length plane: the assembly seats the pin by it.
PIN_END_Y = (-PIN_LENGTH / 2.0, PIN_LENGTH / 2.0)
# -Y end: the lead-in cone.
LEAD_HALF_ANGLE_DEG = 16.0
LEAD_RADIAL = 0.005 * MM_PER_IN
LEAD_END_RADIUS = PIN_RADIUS - LEAD_RADIAL
LEAD_START_Y = PIN_END_Y[0] + LEAD_RADIAL / math.tan(math.radians(LEAD_HALF_ANGLE_DEG))
# +Y end: the crown blend.
CROWN_R = 0.016 * MM_PER_IN
CROWN_CENTRE_R = PIN_RADIUS - CROWN_R
CROWN_CENTRE_Y = PIN_END_Y[1] - CROWN_R

_FLANK = CROWN_CENTRE_Y - LEAD_START_Y
_LEAD_AXIAL = LEAD_START_Y + PIN_LENGTH / 2.0
VOLUME_MM3 = (
    math.pi * PIN_RADIUS**2 * _FLANK
    + math.pi
    * _LEAD_AXIAL
    / 3.0
    * (PIN_RADIUS**2 + PIN_RADIUS * LEAD_END_RADIUS + LEAD_END_RADIUS**2)
    + math.pi
    * (
        CROWN_CENTRE_R**2 * CROWN_R
        + CROWN_CENTRE_R * math.pi * CROWN_R**2 / 2.0
        + 2.0 * CROWN_R**3 / 3.0
    )
)
AREA_MM2 = (
    2.0 * math.pi * PIN_RADIUS * _FLANK
    + math.pi * (PIN_RADIUS + LEAD_END_RADIUS) * math.hypot(_LEAD_AXIAL, LEAD_RADIAL)
    + math.pi * LEAD_END_RADIUS**2
    + math.pi * CROWN_CENTRE_R**2
    + 2.0 * math.pi * CROWN_R * (CROWN_CENTRE_R * math.pi / 2.0 + CROWN_R)
)
FACE_COUNT = 5


async def build_98381A472(adapter, truth=None):
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create dowel section", await adapter.create_sketch("Front"))
    sketch = adapter.currentSketchManager
    bottom, top = PIN_END_Y
    crown_mid = math.radians(45.0)
    with no_sketch_inference(adapter):
        if (
            sketch.CreateCenterLine(
                0.0, (bottom - 1.0) / 1000.0, 0.0, 0.0, (top + 1.0) / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError("98381A472: revolve axis failed")
        if (
            sketch.Create3PointArc(
                PIN_RADIUS / 1000.0,
                CROWN_CENTRE_Y / 1000.0,
                0.0,
                CROWN_CENTRE_R / 1000.0,
                top / 1000.0,
                0.0,
                (CROWN_CENTRE_R + CROWN_R * math.cos(crown_mid)) / 1000.0,
                (CROWN_CENTRE_Y + CROWN_R * math.sin(crown_mid)) / 1000.0,
                0.0,
            )
            is None
        ):
            raise RuntimeError("98381A472: crown arc failed")
        # Arc first, then direct-DB lines (the proven 9275K141 order).
        await add_line_chain(
            adapter,
            [
                (CROWN_CENTRE_R, top),
                (0.0, top),
                (0.0, bottom),
                (LEAD_END_RADIUS, bottom),
                (PIN_RADIUS, LEAD_START_Y),
                (PIN_RADIUS, CROWN_CENTRE_Y),
            ],
            close=False,
        )
    check("exit dowel section", await adapter.exit_sketch())
    name_last_feature(adapter, "DowelSection")
    check(
        "revolve dowel",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "DowelRevolve")
    await volume_check(adapter, "dowel pin", VOLUME_MM3, 0.001 * VOLUME_MM3)
    # Replica frame: revolve axis = model Y; vendor frame: axis = Z.
    adapter._mcm_com_map = lambda v: [v[0], v[2], v[1]]


if __name__ == "__main__":
    sys.exit(replica_main("98381A472", build_98381A472))
