r"""Reproduction script: crank pinion retention pin (book ch. 12 p. 19; 1 used).

The plain straight pin driven radially through the crank pinion's hub boss and
the crankshaft, so the pinion turns with the shaft. ``crank_pinion_spec`` owns
the joint (drill size, station, clocking, the match-drill statement); this pin
is that hole's own drill size, cut flush with the boss on both sides.

Layout: axis Z, one end at the ORIGIN, z 0..PIN_LEN; axisymmetric about its
local x = 0 (the pinion_cam_pin idiom without the crown). In the drive-train
assembly its +Z is laid along machine +X through the pinion's hole.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pinion_pin.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from crank_pinion_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    PIN_DIA,
    PIN_LEN,
)

PART_NAME = "crank-pinion-pin"
MATERIAL = "Plain Carbon Steel"  # drill rod, like the pinion it locks

PIN_R = PIN_DIA / 2.0
V_PIN = math.pi * PIN_R**2 * PIN_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{PIN_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # On-axis pin (origin centre), extruded +Z.
    pin = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        PIN_R,
        "pin",
        dims=pin,
        names=("PinCx", "PinCz", "PinDia"),
        drives=(None, None, '"PinDia"'),
    )
    await ensure_fully_defined(adapter, "pin sketch")
    check("exit_sketch pin", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs += pin.apply(adapter, "PinProfile")
    check(
        "extrude pin",
        await adapter.create_extrusion(ExtrusionParameters(depth=PIN_LEN)),
    )
    name_last_feature(adapter, "Pin")
    depth_dim = name_dimensions(adapter, "Pin", ["PinLen"])
    drive_jobs += [(depth_dim[0], '"PinLen"')]
    volume = await volume_check(adapter, "pin", V_PIN, 0.005 * V_PIN)

    # Named central axis (Axis1): the assembly's lock mates reference the
    # pinion's planes, but a named axis keeps the part mate-ready like every
    # other pin in the fleet.
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pin axis")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pin (equations neutral)", volume, 0.005 * V_PIN)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)

    # Mark the print's two dimensions, author their decimal places natively
    # (policy rule 2) and stamp the title-block properties the sheet reads.
    # No band on either: the match-drilled hole sets the fit.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
