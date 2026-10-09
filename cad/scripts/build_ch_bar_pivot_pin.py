r"""Reproduction script: bar pivot pin (MHA-CH-011; 20 used, one per channel).

The plain 5/64 drill-rod pin that hangs each amplitude bar on its channel
lever (``ch_bar_pivot_pin_spec`` owns the joint and its budget). It RUNS in
the lever's #47 bar-pin hole and is PRESSED into the reamed top pin hole
through both cheeks of the bar's top notch, its ends dressed flush with the
bar's faces (user ruling 2026-10: press fit, removable with a punch).

The model is the INSTALLED pin: a Ø PIN_DIA cylinder PIN_INSTALLED_LENGTH
(the bar's width) long. Layout: pin axis along local X, centred on the origin
(x +-PIN_INSTALLED_LENGTH/2), so the channel assembly seats it with its axis
on the bar's top pin bore and its Right Plane on the bar's mid-width plane.
The pin is a Front-plane half-profile revolved about that axis (the
``build_dt_pinion_lever_pin`` idiom), so its diameter and length both import
into the *Front side view (rule 7, turned parts).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_bar_pivot_pin.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    add_line_chain,
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
    set_dimension_symmetric_tolerance,
)
from _saved_part_guard import require_saved_drawing_properties
from ch_bar_pivot_pin_notes import DRAWING_NOTES
from ch_bar_pivot_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    PIN_DIA,
    PIN_DIA_TOLERANCE,
    PIN_INSTALLED_LENGTH,
)

PART_NAME = "ch-bar-pivot-pin"
MATERIAL = "Plain Carbon Steel"  # drill rod, as the fleet's other drill-rod pins
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
)

PIN_R = PIN_DIA / 2.0
HALF_LEN = PIN_INSTALLED_LENGTH / 2.0
V_PIN = math.pi * PIN_R**2 * PIN_INSTALLED_LENGTH


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{PIN_INSTALLED_LENGTH}mm")

    # Half-profile on the Front Plane (sketch x -> model X, y -> model Y): the
    # axis centerline along X through the origin and the rectangle above it,
    # centred on the origin -- the bar's top pin bore in the assembly. Its two
    # dimensions are the print's two: the length along the outline and the
    # diameter as a doubled centerline-to-outline dim.
    pin = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "axis centerline", await adapter.add_centerline(-HALF_LEN, 0.0, HALF_LEN, 0.0)
    )
    profile_pts = [
        (-HALF_LEN, 0.0),
        (-HALF_LEN, PIN_R),
        (HALF_LEN, PIN_R),
        (HALF_LEN, 0.0),
    ]
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
        PIN_INSTALLED_LENGTH,
        "pin PinLen",
    )
    pin.record("PinLen", '"PinLen"')
    await add_diametric_linear_dimension(
        adapter, axis, outline, (-HALF_LEN / 2.0, PIN_R + 4.0), "PinDia"
    )
    pin.record("PinDia", '"PinDia"')
    start = f"{profile_lines[0]}.start"
    check(
        "pin end on the axis",
        await adapter.add_sketch_constraint(start, "origin", "horizontal_points"),
    )
    await dimension_between(
        adapter,
        start,
        "origin",
        "horizontal_distance",
        HALF_LEN,
        "pin centred on origin",
    )
    pin.record("PinHalfLen", '"PinLen" / 2')
    await ensure_fully_defined(adapter, "pin sketch")
    check("exit_sketch pin", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs = pin.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    volume = await volume_check(adapter, "installed pin", V_PIN, 0.005 * V_PIN)
    res = await adapter.get_mass_properties()
    com = res.data.center_of_mass
    if com is None or any(abs(c) > 1e-6 for c in com):
        raise RuntimeError(f"bar pivot pin is not centred on its origin (COM {com})")

    # Named pin axis (Axis1, along X): coaxial with the bar's top pin bore and
    # the lever's bar-pin hole in the assembly.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Front Plane", 0.0, "pin axis")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pin (equations neutral)", volume, 0.005 * V_PIN)

    # The diameter carries the drill rod's grind band natively (rule 2); the
    # installed length is the bar's width, parenthesized as REFERENCE on the
    # sheet.
    set_dimension_symmetric_tolerance(
        adapter, "PinProfile", "PinDia", PIN_DIA_TOLERANCE
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
