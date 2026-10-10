r"""Reproduction script: rod pivot pin (MHA-CH-010; 20 used, one per channel).

The plain 5/64 drill-rod pin that closes each connecting rod's fork round its
rocker arm (``ch_rod_pivot_pin_spec`` owns the joint and its budget). It RUNS
in the arm's #47 rod hole and is PRESSED into the reamed pin hole through
both tines, its ends dressed flush with the fork's faces (user ruling
2026-10-09, PR #1292 review F1: press fit as the MHA-CH-011 bar pin, removable
with a punch; it reverses the #746 peening reconstruction choice).

The model is the INSTALLED pin: a Ø PIN_DIA cylinder PIN_INSTALLED_LENGTH (the
fork's thickness) long. Layout: axis = part Z, symmetric about the Front Plane
(z = 0, the fork's and the arm's mid-plane). Axis1 is the pin axis (Right
Plane x Top Plane), the assembly's concentric-mate reference.

Built as a REVOLVE of a half-profile on the Right plane (the
``build_dt_crank_pinion_pin`` idiom): a turned part prints its diameter on the
side view beside its length (drawing-simplicity-policy.md rule 7), and only a
dimension whose sketch is parallel to that view imports there natively. A
Right-plane sketch maps local +x -> model -Z; the profile is symmetric, so the
axis line's midpoint on the origin centres the pin on the Front Plane.

``BlankReference`` (blanked, on the Right plane, on the pin axis): the blank's
cut length, a construction line centred on the Front Plane whose one
dimension carries the 2-place band (policy rule 2: the model, not a note,
owns it); the side view prints it below the installed length.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rod_pivot_pin.py
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
    blank_reference_sketches,
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
from _fit_limits import deviations
from _saved_part_guard import require_saved_drawing_properties
from ch_rod_pivot_pin_notes import DRAWING_DIMENSIONS, DRAWING_NOTES, DRAWING_PRECISION
from ch_rod_pivot_pin_spec import (
    PIN_BLANK_LENGTH,
    PIN_BLANK_LENGTH_BAND,
    PIN_DIA,
    PIN_DIA_TOLERANCE,
    PIN_INSTALLED_LENGTH,
)

PART_NAME = "ch-rod-pivot-pin"
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
    await set_global(adapter, "BlankLen", f"{PIN_BLANK_LENGTH}mm")

    # Half-profile on the Right plane (local x -> model -Z, local y -> model
    # Y): the axis line on y = 0 from end to end, each end face rising to the
    # journal, which runs flush face to flush face.
    pin = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Right"))
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
    lines = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    end_a, journal, end_b, axis_line = lines
    for line, direction in (
        (end_a, "vertical"),
        (journal, "horizontal"),
        (end_b, "vertical"),
        (axis_line, "horizontal"),
    ):
        check(
            f"pin {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    # Symmetric about the Front Plane: the axis line's midpoint on the origin.
    check(
        "pin axis midpoint -> origin",
        await adapter.add_sketch_constraint("origin", axis_line, "midpoint"),
    )
    # Installed length between the two flush ends (the fork faces).
    await dimension_between(
        adapter,
        f"{end_a}.end",
        f"{end_b}.start",
        "horizontal_distance",
        PIN_INSTALLED_LENGTH,
        "pin PinLen",
    )
    pin.record("PinLen", '"PinLen"')
    await add_diametric_linear_dimension(
        adapter, axis, journal, (0.0, PIN_R + 4.0), "PinDia"
    )
    pin.record("PinDia", '"PinDia"')
    await ensure_fully_defined(adapter, "pin sketch")
    check("exit_sketch pin", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs = pin.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    volume = await volume_check(adapter, "installed pin", V_PIN, 0.005 * V_PIN)

    # REFERENCE sketch: the blank's cut length, a construction line on the pin
    # axis centred on the Front Plane (the model is the installed pin, so no
    # model edge spans the blank). The side view imports its one dimension.
    blank = SketchDims()
    check("create_sketch blank reference", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    blank_line = check(
        "blank centerline",
        await adapter.add_centerline(
            -PIN_BLANK_LENGTH / 2.0, 0.0, PIN_BLANK_LENGTH / 2.0, 0.0
        ),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "blank centerline horizontal",
        await adapter.add_sketch_constraint(blank_line, None, "horizontal"),
    )
    check(
        "blank centerline midpoint -> origin",
        await adapter.add_sketch_constraint("origin", blank_line, "midpoint"),
    )
    await dimension_between(
        adapter,
        f"{blank_line}.start",
        f"{blank_line}.end",
        "horizontal_distance",
        PIN_BLANK_LENGTH,
        "pin BlankLen",
    )
    blank.record("BlankLen", '"BlankLen"')
    await ensure_fully_defined(adapter, "blank reference sketch")
    check("exit_sketch blank reference", await adapter.exit_sketch())
    name_last_feature(adapter, "BlankReference")
    drive_jobs += blank.apply(adapter, "BlankReference")

    # Axis1: the pin axis, model Z (Right Plane x Top Plane). The channel
    # assembly mates it concentric with the fork's and the arm's pin holes;
    # the Front Plane is the axial mid-plane it aligns with the arm plane.
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

    # The journal carries the drill rod's grind band natively (rule 2); the
    # installed length is the fork's, parenthesized as REFERENCE on the sheet;
    # the blank's cut length carries its own band (the dressing stock,
    # ch_rod_pivot_pin_spec.joint_budget blank_excess_min/max).
    set_dimension_symmetric_tolerance(
        adapter, "PinProfile", "PinDia", PIN_DIA_TOLERANCE
    )
    blank_lower, blank_upper = deviations(PIN_BLANK_LENGTH_BAND)
    if blank_lower != -blank_upper:
        raise AssertionError(
            "ch_rod_pivot_pin_spec.PIN_BLANK_LENGTH_BAND must be symmetric"
        )
    set_dimension_symmetric_tolerance(
        adapter, "BlankReference", "BlankLen", blank_upper
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    blank_reference_sketches(adapter, ("BlankReference",))
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
