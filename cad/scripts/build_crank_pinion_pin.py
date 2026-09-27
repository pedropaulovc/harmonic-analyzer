r"""Reproduction script: crank pinion retention pin (book ch. 12 p. 19; 1 used).

The plain straight pin driven radially through the crank pinion's hub boss and
the crankshaft, so the pinion turns with the shaft. ``crank_pinion_spec`` owns
the joint (drill size, station, clocking, the match-drill statement); this pin
is that hole's own drill size, cut flush with the boss on both sides.

Layout: axis Z, one end at the ORIGIN, z 0..PIN_LEN; axisymmetric about its
local x = 0 (the pinion_cam_pin idiom without the crown). In the drive-train
assembly its +Z is laid along machine +X through the pinion's hole.

Built as a REVOLVE of a half-profile on the Right plane rather than an
extruded circle: a turned part prints its diameter on the side view next to
its length (drawing-simplicity-policy.md rule 7), and only a dimension whose
sketch plane is parallel to that view imports there natively. A Right-plane
sketch maps local +x -> model -Z, so the profile runs x 0..-PIN_LEN.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pinion_pin.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from crank_pinion_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    PIN_DIA,
    PIN_LEN,
)

PART_NAME = "crank-pinion-pin"
MATERIAL = "Plain Carbon Steel"  # drill rod, like the pinion it locks

PIN_R = PIN_DIA / 2.0
V_PIN = math.pi * PIN_R**2 * PIN_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{PIN_LEN}mm")

    # Half-profile on the Right plane (local x -> model -Z, local y -> model
    # Y): the axis centerline on y = 0 from the origin to the far end, and the
    # rectangle above it. Its two dimensions are the print's two dimensions --
    # the length along the outline line, the diameter as a doubled
    # centerline-to-outline dim -- so both import into the side view.
    pin = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "axis centerline", await adapter.add_centerline(0.0, 0.0, -PIN_LEN, 0.0)
    )
    profile_pts = [(0.0, 0.0), (0.0, PIN_R), (-PIN_LEN, PIN_R), (-PIN_LEN, 0.0)]
    profile_lines = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    n = len(profile_lines)
    for i, line in enumerate(profile_lines):
        (_, y1), (_, y2) = profile_pts[i], profile_pts[(i + 1) % n]
        direction = "horizontal" if y1 == y2 else "vertical"
        check(
            f"pin {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    outline = profile_lines[1]
    await dimension_between(
        adapter,
        f"{outline}.start",
        f"{outline}.end",
        "horizontal_distance",
        PIN_LEN,
        "pin PinLen",
    )
    pin.record("PinLen", '"PinLen"')
    await add_diametric_linear_dimension(
        adapter, axis, outline, (-PIN_LEN / 2.0, PIN_R + 4.0), "PinDia"
    )
    pin.record("PinDia", '"PinDia"')
    await anchor_point_to_origin(
        adapter, f"{profile_lines[0]}.start", 0.0, 0.0, "pin anchor"
    )
    await ensure_fully_defined(adapter, "pin sketch")
    check("exit_sketch pin", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs = pin.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
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
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
