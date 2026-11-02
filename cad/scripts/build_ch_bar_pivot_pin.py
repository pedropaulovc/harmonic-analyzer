r"""Reproduction script: bar pivot pin (MHA-CH-11; 20 used, one per channel).

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
into the *Front side view (drawing-guidelines.md rule 11 (turned parts read like the lathe), turned parts).

``BlankReference`` (blanked, on the Front plane, on the pin axis): the blank,
as construction geometry the side view draws thin dashed -- a centerline
on the Right Plane and the blank's two ends run back to the installed pin's
corners -- whose cut length prints at two places under the title block's band
(drawing-simplicity-policy.md `How the repository implements the
guidelines`: the model, not a note, owns it); the side view prints it below
the installed length (the ``build_ch_rod_pivot_pin`` pattern).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_bar_pivot_pin.py
"""

from __future__ import annotations

import math
import sys

from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_properties import part_drawing_unit
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _saved_part_guard import require_saved_drawing_properties
from ch_bar_pivot_pin_notes import DRAWING_DIMENSIONS, DRAWING_NOTES, DRAWING_PRECISION
from ch_bar_pivot_pin_spec import (
    PIN_BLANK_LENGTH,
    PIN_DIA,
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
BLANK_HALF = PIN_BLANK_LENGTH / 2.0
# BlankReference's two ends (mm, Front sketch): a stub along the top edge from
# the installed pin's corner, the blank's end line top -> bottom, and a stub
# back along the bottom edge to the other corner.
BLANK_END_CHAINS: dict[str, tuple[tuple[float, float], ...]] = {
    side: (
        (sign * HALF_LEN, PIN_R),
        (sign * BLANK_HALF, PIN_R),
        (sign * BLANK_HALF, -PIN_R),
        (sign * HALF_LEN, -PIN_R),
    )
    for side, sign in (("left", -1.0), ("right", 1.0))
}


def _as_construction(adapter, entity_id: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{PIN_INSTALLED_LENGTH}mm")
    await set_global(adapter, "BlankLen", f"{PIN_BLANK_LENGTH}mm")

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

    # REFERENCE sketch: the blank, all construction geometry (the sheet draws
    # it thin dashed): a centerline on the pin axis centred on the Right Plane
    # and, at each end, the blank's end line and the two outline stubs that
    # run it back to the installed pin's corners (the model is the installed
    # pin, so no model edge spans the blank). The side view imports its one
    # dimension, the cut length between the dashed ends' lower corners, so
    # its witnesses rise from drawn geometry (ENFORCE review 2026-10-23: a
    # 7.5 BLANK dimensioned to an outline the sheet never drew).
    blank = SketchDims()
    check("create_sketch blank reference", await adapter.create_sketch("Front"))
    ends: dict[str, list[str]] = {}
    set_sketch_direct_db(adapter, True)
    try:
        blank_line = check(
            "blank centerline",
            await adapter.add_centerline(-BLANK_HALF, 0.0, BLANK_HALF, 0.0),
        )
        for side, points in BLANK_END_CHAINS.items():
            ends[side] = await add_line_chain(adapter, list(points), close=False)
    finally:
        # Session state on the seat: a failed segment must not leave sketch
        # inference off for the next leaf.
        set_sketch_direct_db(adapter, False)
    for lines in ends.values():
        for line in lines:
            _as_construction(adapter, line)
    check(
        "blank centerline horizontal",
        await adapter.add_sketch_constraint(blank_line, None, "horizontal"),
    )
    check(
        "blank centerline midpoint -> origin",
        await adapter.add_sketch_constraint("origin", blank_line, "midpoint"),
    )
    for side, axis_end in (("left", "start"), ("right", "end")):
        top, end_line, bottom = ends[side]
        for stub in (top, bottom):
            check(
                f"blank {side} stub {stub} horizontal",
                await adapter.add_sketch_constraint(stub, None, "horizontal"),
            )
        check(
            f"blank {side} end vertical",
            await adapter.add_sketch_constraint(end_line, None, "vertical"),
        )
        check(
            f"blank {side} end centred on the axis",
            await adapter.add_sketch_constraint(
                f"{blank_line}.{axis_end}", end_line, "midpoint"
            ),
        )
    left_end, right_end = ends["left"][1], ends["right"][1]
    check(
        "blank ends equal",
        await adapter.add_sketch_constraint(left_end, right_end, "equal"),
    )
    await dimension_between(
        adapter,
        f"{left_end}.start",
        f"{left_end}.end",
        "vertical_distance",
        PIN_DIA,
        "blank end height",
    )
    blank.record("BlankEndDia", '"PinDia"')
    await dimension_between(
        adapter,
        f"{left_end}.end",
        f"{right_end}.end",
        "horizontal_distance",
        PIN_BLANK_LENGTH,
        "pin BlankLen",
    )
    blank.record("BlankLen", '"BlankLen"')
    # The stubs end at the installed pin's corners.
    for side in ("left", "right"):
        top, _end_line, bottom = ends[side]
        await dimension_between(
            adapter,
            f"{top}.start",
            "origin",
            "horizontal_distance",
            HALF_LEN,
            f"blank {side} stub at the pin end",
        )
        blank.record(f"BlankStub{side.title()}", '"PinLen" / 2')
        check(
            f"blank {side} stubs end square",
            await adapter.add_sketch_constraint(
                f"{top}.start", f"{bottom}.end", "vertical_points"
            ),
        )
    await ensure_fully_defined(adapter, "blank reference sketch")
    check("exit_sketch blank reference", await adapter.exit_sketch())
    name_last_feature(adapter, "BlankReference")
    drive_jobs += blank.apply(adapter, "BlankReference")

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

    # The diameter is the as-bought 5/64 drill rod: untoleranced, the sheet
    # prints it as the stock fraction's REFERENCE (the supplier's grind
    # governs); the installed length is the bar's width, parenthesized as
    # REFERENCE on the sheet; the blank's cut length takes the title block's
    # .XX band (the dressing stock, ch_bar_pivot_pin_spec.joint_budget
    # blank_excess_min/max).
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    blank_reference_sketches(adapter, ("BlankReference",))
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
