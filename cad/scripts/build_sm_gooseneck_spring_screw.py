r"""Build MHA-SM-04, the gooseneck counter-spring clamp screw.

A made slotted fillister shoulder screw turned from 1/2-in 12L14 or 1018
round (owner ruling 2026-10-26 (#1951, option B)).  A plain turned Ø3.50
shoulder under the head is the MHA-SM-VN-51 counter spring's loop seat; a
45-degree lead steps up to the #8-32 UNC thread, which runs into the
gooseneck MHA-SM-01's tapped end plug, and the under-head face clamps the
loop against the plug face.  Sizes and bands live in
``sm_gooseneck_spring_screw_geom``; the print's marks, places and notes in
``sm_gooseneck_spring_screw_spec``.

Layout (``sm_gooseneck_spring_screw_geom`` frame): axis Z, the under-head face
at z=0.  ``HeadProfile`` revolves the cylindrical head and its spherical
crown in +Z (apex at HEAD_H); ``ShankProfile`` revolves the shank in -Z:
the seat shoulder to SHOULDER_LENGTH, the 45-degree lead up to the thread
major, the thread, and a 45-degree tip chamfer.  The thread is modelled as
its basic major cylinder.  The driver slot is sketched on a plane at the apex
and cut SLOT_DEPTH down into the head along local X.  One hidden reference
sketch, ``StationReference``, carries two printed stations only: the overall
length on the axis, and the full-thread limit between two short witnesses
that lie on the under-head face and on the thread's major silhouette.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sm_gooseneck_spring_screw.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _drawing_prefix import set_dimension_prefix
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    anchor_point_to_point,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_rectangle import define_centered_rectangle
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import (
    _named_dimension,
    _named_dimensions,
    apply_drawing_precision,
)
from _drawing_tolerances import _set_tolerance_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from sm_gooseneck_spring_screw_geom import (
    CROWN_CENTER_Z,
    CROWN_RADIUS,
    CROWN_RISE,
    FULL_THREAD_STATION_MAX,
    FULL_THREAD_STATION_MAX_TOL_TYPE,
    HEAD_CYL_H,
    HEAD_DIA,
    HEAD_H,
    LENGTH,
    MAJOR_DIA,
    OVERALL_LENGTH,
    SEAT_DIA,
    SEAT_DIA_LOWER,
    SEAT_DIA_TOL_TYPE,
    SEAT_DIA_UPPER,
    SHOULDER_LENGTH,
    SHOULDER_LENGTH_LOWER,
    SHOULDER_LENGTH_TOL_TYPE,
    SHOULDER_LENGTH_UPPER,
    SLOT_DEPTH,
    SLOT_FLOOR_Z,
    SLOT_WIDTH,
    STEP_LEAD,
    TIP_CHAMFER,
)
from sm_gooseneck_spring_screw_spec import (
    CROWN_RADIUS_PREFIX,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRAWING_PRECISION_BY_NAME,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "sm-gooseneck-spring-screw"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

HEAD_R = HEAD_DIA / 2.0
THREAD_R = MAJOR_DIA / 2.0
SEAT_R = SEAT_DIA / 2.0
# Over-length of the slot rectangle along X: it only has to clear the head.
SLOT_SPAN = HEAD_DIA + 2.0
# StationReference's full-thread witnesses (Right-plane sketch u, v in mm):
# each a short construction line lying ON a visible edge (the under-head face,
# then the thread's major silhouette from the printed station toward the
# tip), so the dimension's extension lines rise from the outline and no
# reference line floats off it.
FULL_THREAD_WITNESS = 0.5
FACE_WITNESS_LINE = ((0.0, THREAD_R), (0.0, THREAD_R + FULL_THREAD_WITNESS))
THREAD_WITNESS_LINE = (
    (FULL_THREAD_STATION_MAX, THREAD_R),
    (FULL_THREAD_STATION_MAX + FULL_THREAD_WITNESS, THREAD_R),
)

# Head: the cylinder plus the spherical cap of sagitta CROWN_RISE.
V_HEAD = math.pi * HEAD_R**2 * HEAD_CYL_H + (
    math.pi * CROWN_RISE**2 * (3.0 * CROWN_RADIUS - CROWN_RISE) / 3.0
)
# Shank: the seat cylinder, the 45-degree lead's frustum (axial length
# STEP_LEAD, seat radius to thread radius) and the thread major cylinder,
# less the tip chamfer's corner triangle (centroid THREAD_R - TIP_CHAMFER/3).
V_SEAT = math.pi * SEAT_R**2 * SHOULDER_LENGTH
V_LEAD = math.pi * STEP_LEAD / 3.0 * (SEAT_R**2 + SEAT_R * THREAD_R + THREAD_R**2)
V_THREAD = math.pi * THREAD_R**2 * (LENGTH - SHOULDER_LENGTH - STEP_LEAD)
V_TIP = math.pi * TIP_CHAMFER**2 * (THREAD_R - TIP_CHAMFER / 3.0)
V_SHANK = V_SEAT + V_LEAD + V_THREAD - V_TIP
V_BODY = V_HEAD + V_SHANK


def slot_strip_area(radius: float, width: float) -> float:
    """Plan area of a centred width-``width`` strip across a radius-``radius`` circle.

    A circle narrower than the strip lies wholly inside it."""
    half = width / 2.0
    if radius <= half:
        return math.pi * radius**2
    return 2.0 * (
        half * math.sqrt(radius**2 - half**2) + radius**2 * math.asin(half / radius)
    )


def crown_radius_at(z: float) -> float:
    """Head radius at height ``z`` (under-head face z=0)."""
    if z <= HEAD_CYL_H:
        return HEAD_R
    return math.sqrt(max(CROWN_RADIUS**2 - (z - CROWN_CENTER_Z) ** 2, 0.0))


def slot_volume(steps: int = 4000) -> float:
    """Head material inside the slot strip above the slot floor.

    The cylindrical part is closed-form; the crown part integrates the strip
    area of each horizontal slice (midpoint rule)."""
    cylinder = slot_strip_area(HEAD_R, SLOT_WIDTH) * (HEAD_CYL_H - SLOT_FLOOR_Z)
    dz = CROWN_RISE / steps
    crown = sum(
        slot_strip_area(crown_radius_at(HEAD_CYL_H + (i + 0.5) * dz), SLOT_WIDTH)
        for i in range(steps)
    )
    return cylinder + crown * dz


V_SLOT = slot_volume()
V_FINAL = V_BODY - V_SLOT


@_telemetry.traced("part.single_limit", label_param="name")
def _single_limit(
    adapter,
    feature: str,
    name: str,
    limit: float,
    tol_type: int,
    lower: float,
    upper: float,
) -> None:
    """``name@feature`` as a single limit: its nominal IS the printed limit
    (swTolMAX / swTolMIN print the nominal plus MAX / MIN), carrying the
    deviations ``lower`` / ``upper`` mm (build_ch_fulcrum_keeper._single_limit's
    recipe)."""
    _, dimension = _named_dimension(adapter, feature, name)
    label = f"{name}@{feature}"
    value = float(dimension.SystemValue)
    if not math.isclose(value, limit / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the limit {limit}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = tol_type
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != tol_type
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: single-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {limit:g} (type {tol_type})")


@_telemetry.traced("part.limit_band", label_param="name")
def _limit_band(
    adapter, feature: str, name: str, deviations: tuple[float, float], tol_type: int
) -> None:
    """A dimension as a native LIMIT band: SOLIDWORKS prints the upper and
    lower limits, the model value plus each deviation, at the dimension's own
    places (build_mg_output_fixture._limit_band), never fewer than the
    deviations need (_drawing_tolerances._set_tolerance_precision)."""
    label = f"{name}@{feature}"
    display, dimension = _named_dimension(adapter, feature, name)
    lower, upper = deviations  # native API order, mm
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = tol_type
    if tolerance.SetValues(lower / 1000.0, upper / 1000.0) is not True:
        raise RuntimeError(f"{label}: LIMIT deviations were rejected")
    if (
        int(tolerance.Type) != tol_type
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: LIMIT tolerance readback changed")
    places = _set_tolerance_precision(
        display, deviations, label=label, places=DRAWING_PRECISION_BY_NAME[name]
    )
    value = float(dimension.SystemValue) * 1000.0
    _telemetry.success(
        f"{label}: LIMIT {value + upper:.{places}f}/{value + lower:.{places}f}"
    )


@_telemetry.traced("part.dimension_callouts")
def _author_dimension_callouts(adapter) -> None:
    """Persist each printed callout on its source dimension, below the value
    (build_mg_magnifying_bracket._author_dimension_callouts): the drawing
    imports and reads them back, never writing them itself."""
    for feature, callouts in DIMENSION_CALLOUTS.items():
        # One walk of the feature's dimension tree for all its callouts.
        resolved = _named_dimensions(adapter, feature, set(callouts))
        for name, text in callouts.items():
            display, _dimension = resolved[name]
            display.SetText(4, text)  # swDimensionTextCalloutBelow
            if str(display.GetText(4) or "").replace("\r\n", "\n") != text:
                raise RuntimeError(f"{name}@{feature}: callout did not persist")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units.
    for name, value in (
        ("HeadDia", HEAD_DIA),
        ("HeadHeight", HEAD_H),
        ("CrownRise", CROWN_RISE),
        ("UnderHeadLength", LENGTH),
        ("ThreadDia", MAJOR_DIA),
        ("SeatDia", SEAT_DIA),
        ("ShoulderLength", SHOULDER_LENGTH),
        ("TipChamfer", TIP_CHAMFER),
        ("FullThread", FULL_THREAD_STATION_MAX),
        ("SlotWidth", SLOT_WIDTH),
        ("SlotDepth", SLOT_DEPTH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Head revolve on the Right plane: sketch (u, v) maps to model (-Z, Y), so
    # the head (+Z) lies at negative u, the apex at u = -HEAD_H.  Rim-to-apex
    # is the minor CCW arc about the crown centre on the axis.
    head = SketchDims()
    u_rim, u_apex, u_centre = -HEAD_CYL_H, -HEAD_H, -CROWN_CENTER_Z
    check("create_sketch head profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "head axis centerline", await adapter.add_centerline(u_apex, 0.0, 0.0, 0.0)
    )
    head_seat, head_side = await add_line_chain(
        adapter, [(0.0, 0.0), (0.0, HEAD_R), (u_rim, HEAD_R)], close=False
    )
    crown = check(
        "head crown arc",
        await adapter.add_arc(u_centre, 0.0, u_rim, HEAD_R, u_apex, 0.0),
    )
    head_close = check("head axis line", await adapter.add_line(u_apex, 0.0, 0.0, 0.0))
    set_sketch_direct_db(adapter, False)
    for line, relation in (
        (head_seat, "vertical"),
        (head_side, "horizontal"),
        (head_close, "horizontal"),
    ):
        check(
            f"head profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    await anchor_point_to_origin(
        adapter, f"{head_seat}.start", 0.0, 0.0, "under-head face centre"
    )
    await dimension_between(
        adapter,
        f"{head_close}.start",
        f"{head_close}.end",
        "horizontal_distance",
        HEAD_H,
        "head height",
    )
    head.record("HeadHeight", '"HeadHeight"')
    await dimension_between(
        adapter,
        f"{head_side}.end",
        f"{head_close}.start",
        "horizontal_distance",
        CROWN_RISE,
        "crown rise",
    )
    head.record("CrownRise", '"CrownRise"')
    await add_diametric_linear_dimension(
        adapter, axis, head_side, (u_rim / 2.0, HEAD_R + 4.0), "HeadDia"
    )
    head.record("HeadDia", '"HeadDia"')
    check(
        "crown radius",
        await adapter.add_sketch_dimension(crown, None, "radial", CROWN_RADIUS),
    )
    head.record(
        "CrownRadius",
        '("HeadDia" / 2 * "HeadDia" / 2 + "CrownRise" * "CrownRise") / (2 * "CrownRise")',
    )
    await ensure_fully_defined(adapter, "head profile sketch")
    check("exit_sketch head profile", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    check("revolve head", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Head")
    await volume_check(adapter, "crowned fillister head", V_HEAD, 0.005 * V_HEAD)

    # Shank revolve on the Right plane, toward +u (model -Z).  The seat runs
    # flat from the under-head face to SHOULDER_LENGTH, the foot of the
    # 45-degree lead that steps up to the thread major.
    shank = SketchDims()
    check("create_sketch shank profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    shank_axis = check(
        "shank axis centerline", await adapter.add_centerline(0.0, 0.0, LENGTH, 0.0)
    )
    points = [
        (0.0, 0.0),
        (0.0, SEAT_R),
        (SHOULDER_LENGTH, SEAT_R),
        (SHOULDER_LENGTH + STEP_LEAD, THREAD_R),
        (LENGTH - TIP_CHAMFER, THREAD_R),
        (LENGTH, THREAD_R - TIP_CHAMFER),
        (LENGTH, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        (u0, v0), (u1, v1) = points[index], points[(index + 1) % len(lines)]
        if u0 != u1 and v0 != v1:
            continue  # the 45-degree lead or tip chamfer: dimensioned below
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"shank profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    seat, step_lead, thread_outline = lines[1], lines[2], lines[3]
    tip_chamfer = lines[4]
    # Every axial size reads from the under-head face, the clamp face.
    for name, start, end, value in (
        ("UnderHeadLength", f"{seat}.start", f"{tip_chamfer}.end", LENGTH),
        ("ShoulderLength", f"{seat}.start", f"{seat}.end", SHOULDER_LENGTH),
        ("TipChamfer", f"{tip_chamfer}.start", f"{tip_chamfer}.end", TIP_CHAMFER),
    ):
        await dimension_between(
            adapter, start, end, "horizontal_distance", value, f"shank {name}"
        )
        shank.record(name, f'"{name}"')
    # The lead's radial leg is the two diameters' half-difference; its axial
    # leg equals it by equation, so the lead is 45 degrees.  The tip chamfer's
    # rise equals its axial leg the same way.
    await dimension_between(
        adapter,
        f"{step_lead}.start",
        f"{step_lead}.end",
        "horizontal_distance",
        STEP_LEAD,
        "shank StepLead",
    )
    shank.record("StepLead", '("ThreadDia" - "SeatDia") / 2')
    await dimension_between(
        adapter,
        f"{tip_chamfer}.start",
        f"{tip_chamfer}.end",
        "vertical_distance",
        TIP_CHAMFER,
        "shank TipChamfer rise",
    )
    shank.record("TipChamferRise", '"TipChamfer"')
    for name, line, u_mid, radius in (
        ("SeatDia", seat, SHOULDER_LENGTH / 2.0, SEAT_R),
        (
            "ThreadDia",
            thread_outline,
            (SHOULDER_LENGTH + STEP_LEAD + LENGTH - TIP_CHAMFER) / 2.0,
            THREAD_R,
        ),
    ):
        await add_diametric_linear_dimension(
            adapter, shank_axis, line, (u_mid, radius + 4.0), name
        )
        shank.record(name, f'"{name}"')
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", 0.0, 0.0, "shank under-head centre"
    )
    await ensure_fully_defined(adapter, "shank profile sketch")
    check("exit_sketch shank profile", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank.apply(adapter, "ShankProfile")
    check("revolve shank", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Shank")
    await volume_check(
        adapter,
        "turned shoulder screw with lead and tip chamfer",
        V_BODY,
        0.005 * V_BODY,
    )

    # Driver slot across the crown: sketched on a plane at the apex and cut
    # down into the head (a cut runs against the plane normal by default).
    check(
        "create_plane SlotPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=HEAD_H
            )
        ),
    )
    name_last_feature(adapter, "SlotPlane")
    plane_dim = name_dimensions(adapter, "SlotPlane", ["ApexStation"])
    drive_jobs.append((plane_dim[0], '"HeadHeight"'))
    slot = SketchDims()
    check("create_sketch driver slot", await adapter.create_sketch("SlotPlane"))
    await define_centered_rectangle(
        adapter,
        SLOT_SPAN / 2.0,
        SLOT_WIDTH / 2.0,
        "driver slot",
        dims=slot,
        name_width="SlotSpan",
        name_depth="SlotWidth",
        drive_depth='"SlotWidth"',
    )
    await ensure_fully_defined(adapter, "driver slot sketch")
    check("exit_sketch driver slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    drive_jobs += slot.apply(adapter, "SlotProfile")
    check(
        "cut driver slot",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=SLOT_DEPTH)),
    )
    name_last_feature(adapter, "DriverSlot")
    drive_jobs.append(
        (name_dimensions(adapter, "DriverSlot", ["SlotDepth"])[0], '"SlotDepth"')
    )
    # A cut the wrong way removes nothing: the volume is the direction check.
    await volume_check(adapter, "slotted shoulder screw", V_FINAL, 0.02 * V_SLOT)
    blank_reference_geometry(adapter, (("SlotPlane", "PLANE"),))

    # Drawing-only station reference.  The apex-to-tip overall, printed as a
    # reference for stock cut-off: one construction line on the axis of the
    # Right plane whose single length dimension IS the printed value (policy
    # drawing-simplicity-policy.md `How the repository implements the guidelines`), driven by the same globals so no geometry moves.
    # The full-thread limit (machinist FIX round 1): the under-head face to
    # the thread-silhouette point at FULL_THREAD_STATION_MAX, between the two
    # witnesses' start points, its value the printed "5.67 MAX".
    stations = SketchDims()
    check("create_sketch station reference", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    try:
        overall_line = check(
            "overall reference line",
            await adapter.add_line(u_apex, 0.0, LENGTH, 0.0),
        )
        (fu0, fv0), (fu1, fv1) = FACE_WITNESS_LINE
        face_witness = check(
            "under-head face witness",
            await adapter.add_line(fu0, fv0, fu1, fv1),
        )
        (tu0, tv0), (tu1, tv1) = THREAD_WITNESS_LINE
        thread_witness = check(
            "full-thread witness",
            await adapter.add_line(tu0, tv0, tu1, tv1),
        )
    finally:
        # Session state on the seat: a failed segment must not leave sketch
        # inference off for the next leaf.
        set_sketch_direct_db(adapter, False)
    for line, relation in (
        (overall_line, "horizontal"),
        (face_witness, "vertical"),
        (thread_witness, "horizontal"),
    ):
        segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(
                f"station reference {line} did not take construction flag"
            )
        check(
            f"station reference {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    await anchor_point_to_origin(
        adapter, f"{overall_line}.start", u_apex, 0.0, "overall reference apex"
    )
    stations.record("ApexReference", '"HeadHeight"')
    await dimension_between(
        adapter,
        f"{overall_line}.start",
        f"{overall_line}.end",
        "horizontal_distance",
        OVERALL_LENGTH,
        "overall length reference",
    )
    stations.record("OverallLength", '"HeadHeight" + "UnderHeadLength"')
    await anchor_point_to_origin(
        adapter, f"{face_witness}.start", fu0, fv0, "face witness on thread radius"
    )
    stations.record("FullThreadRadius", '"ThreadDia" / 2')
    await dimension_between(
        adapter,
        f"{face_witness}.start",
        f"{face_witness}.end",
        "vertical_distance",
        FULL_THREAD_WITNESS,
        "face witness length",
    )
    stations.record("FaceWitness")
    await anchor_point_to_point(
        adapter,
        f"{face_witness}.start",
        f"{thread_witness}.start",
        FULL_THREAD_STATION_MAX,
        0.0,
        "full-thread station",
    )
    stations.record("FullThread", '"FullThread"')
    await dimension_between(
        adapter,
        f"{thread_witness}.start",
        f"{thread_witness}.end",
        "horizontal_distance",
        FULL_THREAD_WITNESS,
        "thread witness length",
    )
    stations.record("ThreadWitness")
    await ensure_fully_defined(adapter, "station reference sketch")
    check("exit_sketch station reference", await adapter.exit_sketch())
    name_last_feature(adapter, "StationReference")
    drive_jobs += stations.apply(adapter, "StationReference")

    # Apply the deferred drive equations once the whole model exists, then
    # re-check neutrality: every equation evaluates to its as-built value.
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter,
        "driven slotted shoulder screw (equations neutral)",
        V_FINAL,
        0.02 * V_SLOT,
    )
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"spring screw: expected one solid body, found {len(bodies)}"
        )

    # Model-owned limits (drawing-simplicity-policy.md `How the repository
    # implements the guidelines`), owner ruling 2026-10-26 (#1951, option B):
    # the seat diameter prints as the LIMIT band 3.60/3.40, its upper limit
    # under the #8-32 2A major minimum so the lead always steps up into the
    # thread blank; the shoulder length (to the lead's foot) as 4.10/3.70, so
    # the loop clears the lead; the full-thread station as the single limit
    # "5.67 MAX" from the under-head face, so full thread starts inside the
    # MHA-SM-01 engagement budget (any shorter run-out only adds engagement,
    # so it carries no deviation).  Every other mark takes the title block's
    # band.
    _limit_band(
        adapter,
        "ShankProfile",
        "SeatDia",
        (SEAT_DIA_LOWER, SEAT_DIA_UPPER),
        SEAT_DIA_TOL_TYPE,
    )
    _limit_band(
        adapter,
        "ShankProfile",
        "ShoulderLength",
        (SHOULDER_LENGTH_LOWER, SHOULDER_LENGTH_UPPER),
        SHOULDER_LENGTH_TOL_TYPE,
    )
    _single_limit(
        adapter,
        "StationReference",
        "FullThread",
        FULL_THREAD_STATION_MAX,
        FULL_THREAD_STATION_MAX_TOL_TYPE,
        0.0,
        0.0,
    )
    # The crown's sphere prints on its arc (machinist FIX round 1): the
    # equation-driven CrownRadius reads "SR"; the drawing parenthesizes it as
    # a reference.
    set_dimension_prefix(adapter, "HeadProfile", "CrownRadius", CROWN_RADIUS_PREFIX)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _author_dimension_callouts(adapter)
    # The station reference owns printed dimensions and only reference lines:
    # hide it so no assembly instance renders it (#880).  The drawing shows it
    # per view through _drawing_hidden_sketches to import those dimensions.
    blank_sketch(adapter, "StationReference")
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
