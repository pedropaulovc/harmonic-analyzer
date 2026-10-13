r"""Reproduction script: pen-height adjuster stud (engineerguy 4/4, 9:15-10:34).

A turned brass stud (pn_pen_adjust_screw_spec): its #0-80 thread runs into
the pen rod's top tap and carries the brass jam nut (vn-pen-adjust-nut); the
eye head above it is cross-drilled for the pen wire. Screwing the stud in or
out sets the pen height against the wire.

Layout (the assembly's contract): origin at the threaded (bottom) end on the
axis, +Y up the axis, the eye's cross hole along X at y = EYE_Y. Axis1 is the
stud axis (Front Plane x Right Plane) for the coaxial mate with the rod's tap.

Built as ONE Right-plane half-profile revolved 360 degrees (StudProfile ->
Stud): the thread's major diameter, its usable full-thread length (the
silhouette is split there, so the revolve leaves the thread-limit edge the
length dimensions from), the head's diameter and height and the overall
length are its named dimensions; the plain shank under the head is what is
left. The profile sits on the Right plane (sketch u -> model -Z, v -> model
Y) rather than the Front, so the *Right side view -- the one that sees the X
cross hole end-on as a circle -- imports every marked dimension
(pn_pen_adjust_screw_spec.DRAWING_DIMENSIONS). The #54 eye is a native Hole
Wizard drill (EyeHole) radially through the head, placed on EyeStationPlane;
its printed station EyeFromHeadEnd (from the head's faced end) rides the
hidden Right-plane reference sketch EyeStationReference, because the wizard's
cylindrical placement sketch carries no dimension. The thread carries a
blind cosmetic #0-80 over the full-thread length so the isometric matches the
callout.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_adjust_screw.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _holes import cross_hole_volume_mm3, wizard_hole_on_cylinder
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from pn_pen_adjust_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    EYE_DIA,
    EYE_FROM_HEAD_END,
    EYE_SPEC,
    EYE_Y,
    FULL_THREAD_LENGTH,
    HEAD_DIA,
    HEAD_HEIGHT,
    OVERALL_LENGTH,
    SHANK_LENGTH,
    THREAD,
    THREAD_MAJOR,
)

PART_NAME = "pn-pen-adjust-screw"
MATERIAL = "Brass"  # see _appearance.apply_material docstring
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
)
# The eye's station from the threaded end (the plane the wizard drills on)
# and from the head's faced end (the printed one), as the drive equations
# state them.
EYE_Y_EXPR = '"OverallLength" - "HeadHeight" / 2'
EYE_FROM_HEAD_END_EXPR = '"HeadHeight" / 2'

THREAD_R = THREAD_MAJOR / 2.0
HEAD_R = HEAD_DIA / 2.0
V_SHANK = math.pi * THREAD_R**2 * SHANK_LENGTH
V_HEAD = math.pi * HEAD_R**2 * HEAD_HEIGHT
V_STUD = V_SHANK + V_HEAD
# The through drill crosses the full head diameter on its axis.
V_EYE = cross_hole_volume_mm3(EYE_DIA, HEAD_DIA)
V_TOTAL = V_STUD - V_EYE


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        AddThreadParameters,
        CreatePlaneParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units. Each profile dim below is driven from these via the
    # deferred drive batch.
    for name, value in (
        ("ThreadDia", THREAD_MAJOR),
        ("FullThreadLength", FULL_THREAD_LENGTH),
        ("HeadDia", HEAD_DIA),
        ("HeadHeight", HEAD_HEIGHT),
        ("OverallLength", OVERALL_LENGTH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Half-section on the Right plane (sketch u = -z, v = y): the flat threaded
    # end on the origin, the full thread at its basic major, the plain shank
    # (same diameter, its own segment so the revolve leaves the thread-limit
    # edge) up to the head's shoulder, the head, the faced top, and the
    # closure back down the axis.
    profile = SketchDims()
    check("create_sketch stud profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "stud axis centerline",
        await adapter.add_centerline(0.0, 0.0, 0.0, OVERALL_LENGTH),
    )
    points = [
        (0.0, 0.0),
        (THREAD_R, 0.0),
        (THREAD_R, FULL_THREAD_LENGTH),
        (THREAD_R, SHANK_LENGTH),
        (HEAD_R, SHANK_LENGTH),
        (HEAD_R, OVERALL_LENGTH),
        (0.0, OVERALL_LENGTH),
    ]
    end, thread, shank, shoulder, head, top, closure = await add_line_chain(
        adapter, points
    )
    set_sketch_direct_db(adapter, False)
    for label, first, second in (
        ("axis start", f"{axis}.start", f"{end}.start"),
        ("axis end", f"{axis}.end", f"{top}.end"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, "coincident"))
    for label, entity, relation in (
        ("threaded end", end, "horizontal"),
        ("thread", thread, "vertical"),
        ("plain shank", shank, "vertical"),
        ("shoulder", shoulder, "horizontal"),
        ("head", head, "vertical"),
        ("top", top, "horizontal"),
        ("closure", closure, "vertical"),
        ("axis", axis, "vertical"),
    ):
        check(label, await adapter.add_sketch_constraint(entity, None, relation))
    await anchor_point_to_origin(adapter, f"{end}.start", 0.0, 0.0, "threaded end")
    await add_diametric_linear_dimension(
        adapter, axis, thread, (THREAD_R + 4.0, FULL_THREAD_LENGTH / 2.0), "ThreadDia"
    )
    profile.record("ThreadDia", '"ThreadDia"')
    # Lengths (drawing-guidelines.md rules 10/11): the usable full thread from
    # the faced threaded end; the head from its own faced end to the shoulder;
    # the overall from end to end. The plain shank is what is left.
    check(
        "full thread length",
        await adapter.add_sketch_dimension(thread, None, "linear", FULL_THREAD_LENGTH),
    )
    profile.record("FullThreadLength", '"FullThreadLength"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        head,
        (HEAD_R + 4.0, SHANK_LENGTH + HEAD_HEIGHT / 2.0),
        "HeadDia",
    )
    profile.record("HeadDia", '"HeadDia"')
    check(
        "head height",
        await adapter.add_sketch_dimension(head, None, "linear", HEAD_HEIGHT),
    )
    profile.record("HeadHeight", '"HeadHeight"')
    await dimension_between(
        adapter,
        f"{end}.start",
        f"{top}.end",
        "vertical_distance",
        OVERALL_LENGTH,
        "overall length, threaded end to head end",
    )
    profile.record("OverallLength", '"OverallLength"')
    await ensure_fully_defined(adapter, "stud profile")
    check("exit_sketch stud profile", await adapter.exit_sketch())
    name_last_feature(adapter, "StudProfile")
    drive_jobs += profile.apply(adapter, "StudProfile")
    check("revolve stud", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Stud")
    await volume_check(adapter, "stud", V_STUD, 0.005 * V_STUD)

    # The #54 eye: a native Hole Wizard drill radially into the head's
    # cylinder at +X, through-all so it leaves by the far wall. Its station
    # rides an offset plane (driven from the head's mid-height); the Front
    # plane holds it on the axis.
    check(
        "create_plane EyeStationPlane",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=EYE_Y)
        ),
    )
    name_last_feature(adapter, "EyeStationPlane")
    drive_jobs.append(
        (
            name_dimensions(adapter, "EyeStationPlane", ["EyeStationOffset"])[0],
            EYE_Y_EXPR,
        )
    )
    wizard_hole_on_cylinder(
        adapter,
        EYE_SPEC,
        [HEAD_R, EYE_Y, 0.0],
        "pen-wire eye",
        name="EyeHole",
        point_planes=("EyeStationPlane", "Front Plane"),
    )
    volume = await volume_check(adapter, "eye cross hole", V_TOTAL, 0.02 * V_EYE)

    # Drawing-only station reference: a construction line down the axis from
    # the head's faced end to the eye, whose printed dimension is the eye's
    # station from that face (drawing-guidelines.md rule 11: head features
    # from the head's own faced end). Its other dimension only seats the
    # line's top on the head end; it is never marked. On the Right plane, the
    # plane of the side view that prints it.
    station = SketchDims()
    check("create_sketch eye station", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    station_line = check(
        "eye station reference line",
        await adapter.add_line(0.0, EYE_Y, 0.0, OVERALL_LENGTH),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[station_line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("eye station reference did not take the construction flag")
    check(
        "eye station reference vertical",
        await adapter.add_sketch_constraint(station_line, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter,
        f"{station_line}.end",
        0.0,
        OVERALL_LENGTH,
        "eye station reference on the head end",
    )
    station.record("HeadEndStation", '"OverallLength"')
    await dimension_between(
        adapter,
        f"{station_line}.start",
        f"{station_line}.end",
        "vertical_distance",
        EYE_FROM_HEAD_END,
        "eye station from the head end",
    )
    station.record("EyeFromHeadEnd", EYE_FROM_HEAD_END_EXPR)
    await ensure_fully_defined(adapter, "eye station reference sketch")
    check("exit_sketch eye station", await adapter.exit_sketch())
    name_last_feature(adapter, "EyeStationReference")
    drive_jobs += station.apply(adapter, "EyeStationReference")

    # Named stud axis (local Y through the origin): the assembly mates it
    # coaxial with the rod's top tap.
    stud_axis = await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "stud axis"
    )
    if stud_axis != "Axis1":
        raise RuntimeError(
            f"stud axis must be Axis1 for the assembly, got {stud_axis!r}"
        )

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    driven = await volume_check(
        adapter, "driven stud (equations neutral)", volume, 0.001 * volume
    )

    # Cosmetic #0-80 from the threaded end's edge, blind over the usable full
    # thread to the thread-limit edge, so the shaded isometric shows the
    # thread the callout names and where it stops. It cuts nothing.
    adapter._zoom_to_fit(adapter.currentModel)
    check(
        f"cosmetic thread {THREAD}",
        await adapter.add_thread(
            AddThreadParameters(
                edge_point=[THREAD_R, 0.0, 0.0],
                standard="ansi_inch",
                size=THREAD,
                end_type="blind",
                depth=FULL_THREAD_LENGTH,
            )
        ),
    )
    await volume_check(adapter, "cosmetic thread cuts nothing", driven, 1e-6)
    blank_reference_geometry(adapter, (("EyeStationPlane", "PLANE"),))

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(adapter, PART_NAME)
    # The reference sketch owns a printed dimension but no geometry: hide it
    # so no assembly instance renders it; the drawing shows it in the side
    # view only (_drawing_hidden_sketches) to import EyeFromHeadEnd.
    blank_sketch(adapter, "EyeStationReference")
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
