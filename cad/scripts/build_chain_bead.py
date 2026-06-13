r"""Reproduction script: chain bead (book ch. 23/30).

One ball of the bead chain that loops the two chain-wrapped removable
gears (T12 crank shaft -> T24 knob shaft). The full chain is a SolidWorks
chain component pattern in build_output_assembly.py: BEAD_COUNT beads at
the exact-closure BEAD_PITCH along the closed centreline loop from
_chain.py (which replaced the rigid flat-band stand-in part).

Sphere O4.8 (ball-chain trade size #13: ball 4.76, pitch 6.35 -- see the
_chain.py provenance comments); the connecting wire between beads is a
flexible element, not modeled. A reference axis along the part Z axis
(normal to the machine chain plane) is the chain pattern's path-alignment
geometry: the pattern puts the axis ON the path sketch, centring every
bead on the centreline.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_chain_bead.py
"""

from __future__ import annotations

import math
import sys

from _chain import BEAD_R
from _common import (
    BAR_STEEL,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "chain-bead"
MATERIAL = "Plain Carbon Steel"  # bead chain reads mid-grey in the plates
AXIS_NAME = "Axis1"  # build_output_assembly selects "<AXIS_NAME>@<comp>@output"


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreateAxisParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    r = BEAD_R
    check("create_sketch bead profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "axis centerline",
        await adapter.add_centerline(0.0, -r, 0.0, r),
    )
    arc = check(
        "add bead arc",
        # CCW from -90 deg to +90 deg through +X: the +x half disc.
        await adapter.add_arc(0.0, 0.0, 0.0, -r, 0.0, r),
    )
    closer = check("add closing line", await adapter.add_line(0.0, r, 0.0, -r))
    set_sketch_direct_db(adapter, False)
    # Half-disc scheme: the closing line and centerline merged into the arc
    # endpoints at creation, so four constraints finish it -- centre on the
    # origin, the radius, the closing line vertical (pinning the chord's
    # direction), and the arc start straight under the centre (pinning the
    # chord onto the diameter; the merged endpoints carry the centerline).
    await anchor_point_to_origin(adapter, f"{arc}.center", 0.0, 0.0, "bead centre")
    check(
        "bead radius",
        await adapter.add_sketch_dimension(arc, None, "radial", r),
    )
    check(
        "closing line vertical",
        await adapter.add_sketch_constraint(closer, None, "vertical"),
    )
    check(
        "arc start under centre",
        await adapter.add_sketch_constraint(
            f"{arc}.start", f"{arc}.center", "vertical_points"
        ),
    )
    await ensure_fully_defined(adapter, "bead profile")
    check("exit_sketch bead profile", await adapter.exit_sketch())
    check("revolve bead", await adapter.create_revolve(RevolveParameters(angle=360.0)))

    expected = 4.0 / 3.0 * math.pi * r**3
    res = await adapter.get_mass_properties()
    vol = float(res.data.volume) if res.is_success else float("nan")
    print(f"  volume: {vol:.2f} mm^3 (analytic {expected:.2f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"bead volume {vol:.2f} != {expected:.2f}")

    # Path-alignment axis for the chain component pattern: part Z (the
    # bead is authored with the machine chain plane as its XY plane).
    axis = check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    )
    if axis.name != AXIS_NAME:
        raise RuntimeError(
            f"path-alignment axis is {axis.name!r}, build_output_assembly"
            f" selects {AXIS_NAME!r} -- keep them in sync"
        )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, BAR_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
