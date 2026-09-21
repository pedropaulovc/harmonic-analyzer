r"""Build the pinion-handle retention pin.

The pin is a straight, flat-ended cylinder on local +Z, from the origin at
z=0 through ``PIN_LEN``.  A Right-plane half-profile is revolved so the native
``PinDia`` and ``PinLen`` dimensions import together into the side view.  The
assembly maps this axis to the handle's local +Y and centres the pin on the
arbor at local z=5.0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_handle_pin.py
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
from pinion_handle_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    PIN_DIA,
    PIN_LEN,
)


PART_NAME = "pinion-handle-pin"
MATERIAL = "Plain Carbon Steel"  # AISI 1018 cold-finished registry material

PIN_R = PIN_DIA / 2.0
V_PIN = math.pi * PIN_R**2 * PIN_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing in the
    # inch document; the equation manager reads bare values in document units.
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{PIN_LEN}mm")

    # Half-profile on the Right plane (local x -> model -Z, local y -> model
    # Y).  Revolving the rectangle gives a flat-ended cylinder whose model
    # axis runs from z=0 to +PIN_LEN.
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

    # Named central axis for the handle assembly's +Y mate.
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pin axis")

    # Deferred drive equations, then re-check neutrality: each evaluates to the
    # as-built value, so equation authoring cannot silently alter the solid.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pin (equations neutral)", volume, 0.005 * V_PIN)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)

    # Mark exactly the two print dimensions and author their decimal places on
    # the part. The drawing reads these native values back; it never rewrites
    # precision or adds an independent fit band.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
