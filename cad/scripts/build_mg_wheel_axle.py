r"""Reproduction script: magnifying-wheel axle (book ch. 21, pp. 50-51).

A plain pin from 3/16 drill rod (mg_wheel_axle_spec): pressed into the
mg-wheel-bar's reamed bore until the shank stands the press gauge off the
bar's front face, the back end then about flush with its back face; the
magnifying wheel runs on the shank; the front end is a #4-40 thread for the
nut and locknut, finished with a domed tip. ``mg_wheel_group`` sizes the
lengths against the whole stack.

Layout: pin axis local +Y, origin on the bar's FRONT face (the assembly's
d = 0); back end y = BACK_Y (-9), shank to STEP_Y (the gauge), thread to
THREAD_END_Y, dome to TIP_Y. The assembly mates Axis1 and the Front Plane.

Built as ONE Front-plane revolve (PinProfile -> Pin): every printed diameter
and length is a named dimension in that sketch, so the drawing inserts them
as model items (mg_wheel_axle_spec.DRAWING_DIMENSIONS).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_wheel_axle.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from mg_wheel_axle_spec import (
    BACK_Y,
    DOME_H,
    DOME_R,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    PIN_DIA,
    PIN_DIA_TOL,
    PIN_LEN,
    PRESS_GAUGE,
    SHANK_LEN,
    SHANK_LEN_BAND,
    STEP_Y,
    THREAD_END_Y,
    THREAD_LEN,
    THREAD_LEN_BAND,
    THREAD_MAJOR,
    TIP_Y,
)

PART_NAME = "mg-wheel-axle"
MATERIAL = "Plain Carbon Steel"  # drill rod, as the fleet's other drill-rod pins
PIN_R = PIN_DIA / 2.0
THREAD_R = THREAD_MAJOR / 2.0
V_SHANK = math.pi * PIN_R**2 * SHANK_LEN
V_THREAD = math.pi * THREAD_R**2 * THREAD_LEN
V_DOME = math.pi * DOME_H**2 * (3.0 * DOME_R - DOME_H) / 3.0
V_TOTAL = V_SHANK + V_THREAD + V_DOME


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units. Each profile dim below is driven from these via the
    # deferred drive batch.
    for name, value in (
        ("PinDia", PIN_DIA),
        ("ShankLength", SHANK_LEN),
        ("ThreadDia", THREAD_MAJOR),
        ("ThreadLength", THREAD_LEN),
        ("DomeHeight", DOME_H),
        ("PressGauge", PRESS_GAUGE),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Half-section about local +Y (Front sketch u, v = model x, y): flat back
    # end, shank, step, thread at the basic major, spherical dome to the tip.
    profile = SketchDims()
    check("create_sketch pin profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check("pin axis", await adapter.add_centerline(0.0, BACK_Y, 0.0, TIP_Y))
    points = [
        (0.0, BACK_Y),
        (PIN_R, BACK_Y),
        (PIN_R, STEP_Y),
        (THREAD_R, STEP_Y),
        (THREAD_R, THREAD_END_Y),
    ]
    back_end, shank, step, thread = await add_line_chain(adapter, points, close=False)
    dome = check(
        "dome arc",
        await adapter.add_arc(0.0, TIP_Y - DOME_R, THREAD_R, THREAD_END_Y, 0.0, TIP_Y),
    )
    closure = check("pin closure", await adapter.add_line(0.0, TIP_Y, 0.0, BACK_Y))
    set_sketch_direct_db(adapter, False)
    for label, first, second in (
        ("thread-dome", f"{thread}.end", f"{dome}.start"),
        ("dome-closure", f"{dome}.end", f"{closure}.start"),
        ("closure-back", f"{closure}.end", f"{back_end}.start"),
        ("axis start", f"{axis}.start", f"{back_end}.start"),
        ("axis end", f"{axis}.end", f"{dome}.end"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, "coincident"))
    for label, entity, relation in (
        ("back end", back_end, "horizontal"),
        ("shank", shank, "vertical"),
        ("step", step, "horizontal"),
        ("thread", thread, "vertical"),
        ("closure", closure, "vertical"),
        ("axis", axis, "vertical"),
    ):
        check(label, await adapter.add_sketch_constraint(entity, None, relation))
    await anchor_point_to_origin(
        adapter, f"{back_end}.start", 0.0, BACK_Y, "pin back end"
    )
    profile.record("BackEnd", '"ShankLength" - "PressGauge"')
    await add_diametric_linear_dimension(
        adapter, axis, shank, (PIN_R + 4.0, (BACK_Y + STEP_Y) / 2.0), "PinDia"
    )
    profile.record("PinDia", '"PinDia"')
    check(
        "shank length",
        await adapter.add_sketch_dimension(shank, None, "linear", SHANK_LEN),
    )
    profile.record("ShankLength", '"ShankLength"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        thread,
        (THREAD_R + 4.0, (STEP_Y + THREAD_END_Y) / 2.0),
        "ThreadDia",
    )
    profile.record("ThreadDia", '"ThreadDia"')
    check(
        "thread length",
        await adapter.add_sketch_dimension(thread, None, "linear", THREAD_LEN),
    )
    profile.record("ThreadLength", '"ThreadLength"')
    # Overall from the back end's outer corner (where the drawing's extension
    # lines rise).
    await dimension_between(
        adapter,
        f"{shank}.start",
        f"{closure}.start",
        "vertical_distance",
        PIN_LEN,
        "pin length",
    )
    profile.record("PinLength", '"ShankLength" + "ThreadLength" + "DomeHeight"')
    check(
        "dome radius",
        await adapter.add_sketch_dimension(dome, None, "radial", DOME_R),
    )
    profile.record(
        "DomeR",
        '("ThreadDia" / 2 * "ThreadDia" / 2 + "DomeHeight" * "DomeHeight") '
        '/ (2 * "DomeHeight")',
    )
    await ensure_fully_defined(adapter, "pin profile")
    check("exit_sketch pin profile", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs += profile.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    await volume_check(adapter, "pin", V_TOTAL, 0.005 * V_TOTAL)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pin (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )

    # Named pin axis (local Y through the origin) so the magnifying wheel
    # revolves on it in the mated-DOF assembly (Axis1).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "pin axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_symmetric_tolerance(adapter, "PinProfile", "PinDia", PIN_DIA_TOL)
    set_dimension_bilateral_tolerance(
        adapter, "PinProfile", "ShankLength", *deviations(SHANK_LEN_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "PinProfile", "ThreadLength", *deviations(THREAD_LEN_BAND)
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
