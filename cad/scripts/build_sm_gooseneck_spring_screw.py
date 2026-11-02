r"""Build MHA-SM-04, the gooseneck counter-spring clamp screw.

A made slotted cheese-head screw turned from 1/2-in 4140 hardened to HRC 32,
the grade its clamp strength needs (owner rulings 2026-10-27, #1951).  Under
the flat-topped Ø11.50 x 6.60 head, a plain Ø6.35 body is the MHA-SM-VN-51
counter spring's loop seat.  It is also the 1/4-28 UNF thread's own blank,
turned to its LIMIT band, and the die cuts the thread on it toward the tip.
The thread runs into the blind 1/4-28 tap in the solid end piece of the
gooseneck MHA-SM-01, and the under-head face clamps the loop against the end
piece's flush face.  Sizes and bands live in
``sm_gooseneck_spring_screw_geom``; the print's marks, places and notes in
``sm_gooseneck_spring_screw_spec``.

Layout (``sm_gooseneck_spring_screw_geom`` frame): axis Z, the under-head face
at z=0.  ``HeadProfile`` revolves the flat-topped cylinder head in +Z (top
face at HEAD_H), its under-face edge relieved by a 45-degree chamfer for the
loop's transition wire; ``ShankProfile`` revolves the body in -Z: one plain
cylinder from the R.020 MAX under-head corner to a 45-degree tip chamfer.  The
body and the thread share the basic major cylinder; the thread callout defines
the thread.  The driver slot is sketched on a plane at the top face and cut
SLOT_DEPTH down into the head along local X.  One hidden reference sketch,
``StationReference``, carries three printed stations only: the overall length
on the axis, and the plain length's MIN and the full-thread station's MAX,
each between a short witness on the under-head face and one on the body's
silhouette.

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
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
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
from _single_limit_tolerance import set_single_limit
from _visibility import blank_reference_geometry
from sm_gooseneck_spring_screw_geom import (
    BODY_DIA,
    BODY_DIA_TOL_TYPE,
    FULL_THREAD_STATION_MAX,
    FULL_THREAD_STATION_MAX_BAND,
    FULL_THREAD_STATION_MAX_TOL_TYPE,
    HEAD_DIA,
    HEAD_DIA_TOL_TYPE,
    HEAD_H,
    HEAD_RELIEF_CHAMFER,
    HEAD_RELIEF_CHAMFER_TOL_TYPE,
    LENGTH,
    OVERALL_LENGTH,
    PLAIN_LENGTH_MIN,
    PLAIN_LENGTH_MIN_BAND,
    PLAIN_LENGTH_MIN_TOL_TYPE,
    SLOT_DEPTH,
    SLOT_WIDTH,
    THREAD,
    THREAD_SIZE,
    TIP_CHAMFER,
    UNDERHEAD_CORNER_R,
    UNDERHEAD_CORNER_R_BAND,
    UNDERHEAD_CORNER_R_TOL_TYPE,
)
from sm_gooseneck_spring_screw_spec import (
    DIMENSION_CALLOUTS,
    DIMENSION_CALLOUTS_ABOVE,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRAWING_PRECISION_BY_NAME,
    ISOMETRIC_VIEW_NOTE,
    PRINTED_BANDS,
    UNIT,
)

PART_NAME = "sm-gooseneck-spring-screw"
# The library stand-in for the registry's 4140 (7.80 g/cc against 7.85); the
# printed grade is the config row's (see _appearance.apply_material).
MATERIAL = "Plain Carbon Steel"
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

HEAD_R = HEAD_DIA / 2.0
BODY_R = BODY_DIA / 2.0
# The under-head corner round (Right-plane sketch u, v in mm): its centre off
# the face and the body by its radius, its CCW quarter from the face to the
# body.
CORNER_CENTER = (UNDERHEAD_CORNER_R, BODY_R + UNDERHEAD_CORNER_R)
CORNER_FACE_TANGENT = (0.0, BODY_R + UNDERHEAD_CORNER_R)
CORNER_BODY_TANGENT = (UNDERHEAD_CORNER_R, BODY_R)
# Over-length of the slot rectangle along X: it only has to clear the head.
SLOT_SPAN = HEAD_DIA + 2.0
# StationReference's witnesses (Right-plane sketch u, v in mm): each a short
# construction line lying ON a visible edge (the under-head face from the
# corner round's tangent point up, then the body's silhouette from each
# printed station toward the tip), so the dimensions' extension lines rise
# from the outline and no reference line floats off it.
STATION_WITNESS = 0.5
FACE_WITNESS_LINE = (
    CORNER_FACE_TANGENT,
    (0.0, CORNER_FACE_TANGENT[1] + STATION_WITNESS),
)
PLAIN_WITNESS_LINE = (
    (PLAIN_LENGTH_MIN, BODY_R),
    (PLAIN_LENGTH_MIN + STATION_WITNESS, BODY_R),
)
THREAD_WITNESS_LINE = (
    (FULL_THREAD_STATION_MAX, BODY_R),
    (FULL_THREAD_STATION_MAX + STATION_WITNESS, BODY_R),
)
# The face witness stays under the head's rim, the body witnesses apart and
# short of the tip chamfer.
if FACE_WITNESS_LINE[1][1] >= HEAD_R:
    raise AssertionError("under-head face witness runs off the head")
if not (
    CORNER_BODY_TANGENT[0]
    < PLAIN_WITNESS_LINE[0][0]
    < PLAIN_WITNESS_LINE[1][0]
    < THREAD_WITNESS_LINE[0][0]
    < THREAD_WITNESS_LINE[1][0]
    < LENGTH - TIP_CHAMFER
):
    raise AssertionError("station witnesses overlap or leave the plain body")
# The cosmetic thread (model x, y, z in mm; the shank runs down -Z): seeded on
# the circular edge where the tip chamfer meets the body, run toward the head
# to the full-thread station's MAX, so its end line stands on that station's
# witness.
THREAD_EDGE_POINT = (0.0, BODY_R, -(LENGTH - TIP_CHAMFER))
COSMETIC_THREAD_DEPTH = LENGTH - TIP_CHAMFER - FULL_THREAD_STATION_MAX
if not 0.0 < COSMETIC_THREAD_DEPTH < LENGTH - TIP_CHAMFER - PLAIN_LENGTH_MIN:
    raise AssertionError("cosmetic thread leaves the threaded body")

# Head: the flat-topped cylinder less the relief chamfer's corner triangle
# (centroid HEAD_R - HEAD_RELIEF_CHAMFER/3).
V_HEAD = math.pi * HEAD_R**2 * HEAD_H - math.pi * HEAD_RELIEF_CHAMFER**2 * (
    HEAD_R - HEAD_RELIEF_CHAMFER / 3.0
)
# Shank: the body cylinder less the tip chamfer's corner triangle (centroid
# BODY_R - TIP_CHAMFER/3), plus the under-head corner round: its spandrel,
# (1 - pi/4) R^2, swept about the axis at its centroid, (10 - 3 pi) /
# (12 - 3 pi) R off both legs (Pappus; build_mg_magnifying_vertical_rod's
# relief roots).
V_BODY_CYLINDER = math.pi * BODY_R**2 * LENGTH
V_TIP = math.pi * TIP_CHAMFER**2 * (BODY_R - TIP_CHAMFER / 3.0)
_CORNER_SPANDREL = (1.0 - math.pi / 4.0) * UNDERHEAD_CORNER_R**2
_CORNER_CENTROID_R = (
    BODY_R + (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi) * UNDERHEAD_CORNER_R
)
V_CORNER = 2.0 * math.pi * _CORNER_CENTROID_R * _CORNER_SPANDREL
V_SHANK = V_BODY_CYLINDER - V_TIP + V_CORNER
V_TURNED = V_HEAD + V_SHANK


def slot_strip_area(radius: float, width: float) -> float:
    """Plan area of a centred width-``width`` strip across a radius-``radius`` circle.

    A circle narrower than the strip lies wholly inside it."""
    half = width / 2.0
    if radius <= half:
        return math.pi * radius**2
    return 2.0 * (
        half * math.sqrt(radius**2 - half**2) + radius**2 * math.asin(half / radius)
    )


# The slot: the strip across the flat top, SLOT_DEPTH deep.
V_SLOT = slot_strip_area(HEAD_R, SLOT_WIDTH) * SLOT_DEPTH
V_FINAL = V_TURNED - V_SLOT


async def _volume_check(adapter, label: str, expected: float, tol: float) -> float:
    # NaN passes every |vol - expected| > tol comparison (the shared
    # volume_check's included, #2013), so a non-finite read stops the build
    # (codjiflo on #1997, as build_sm_gooseneck).
    volume = await volume_check(adapter, label, expected, tol)
    if not math.isfinite(volume):
        raise RuntimeError(f"{label}: non-finite volume {volume!r}")
    return volume


@_telemetry.traced("part.limit_band", label_param="name")
def _limit_band(
    adapter,
    feature: str,
    name: str,
    model: float,
    deviations: tuple[float, float],
    tol_type: int,
) -> None:
    """A dimension as a native LIMIT band: SOLIDWORKS prints the upper and
    lower limits, the model value plus each deviation, at the dimension's own
    places (build_mg_output_fixture._limit_band).  #290: the mm model is off
    the inch grid, so the deviations are not; the printed LIMITS are, and they
    set the places (_drawing_tolerances._set_tolerance_precision).  The limits
    come from the spec's ``model`` (mm), never the read-back SystemValue,
    whose inch-document float noise would need more than eight places."""
    label = f"{name}@{feature}"
    display, dimension = _named_dimension(adapter, feature, name)
    value = float(dimension.SystemValue) * 1000.0
    if not math.isclose(value, model, abs_tol=1e-6):
        raise RuntimeError(f"{label}: nominal {value!r} mm is not the spec's {model!r}")
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
        display,
        (model + lower, model + upper),
        display_unit=UNIT,
        label=label,
        places=DRAWING_PRECISION_BY_NAME[name],
    )
    _telemetry.success(
        f"{label}: LIMIT {(model + upper) / 25.4:.{places}f}/"
        f"{(model + lower) / 25.4:.{places}f} in"
    )


@_telemetry.traced("part.dimension_callouts")
def _author_dimension_callouts(adapter) -> None:
    """Persist each printed callout on its source dimension, below or above
    the value (build_mg_magnifying_bracket._author_dimension_callouts): the
    drawing imports and reads them back, never writing them itself."""
    # swDimensionTextCalloutBelow = 4, swDimensionTextCalloutAbove = 3.
    for slot, by_feature in ((4, DIMENSION_CALLOUTS), (3, DIMENSION_CALLOUTS_ABOVE)):
        for feature, callouts in by_feature.items():
            # One walk of the feature's dimension tree for all its callouts.
            resolved = _named_dimensions(adapter, feature, set(callouts))
            for name, text in callouts.items():
                display, _dimension = resolved[name]
                display.SetText(slot, text)
                if str(display.GetText(slot) or "").replace("\r\n", "\n") != text:
                    raise RuntimeError(f"{name}@{feature}: callout did not persist")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        AddThreadParameters,
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The mm suffix is load-bearing (INCH document): the equation manager reads
    # bare numbers in document units.
    for name, value in (
        ("HeadDia", HEAD_DIA),
        ("HeadHeight", HEAD_H),
        ("HeadReliefChamfer", HEAD_RELIEF_CHAMFER),
        ("UnderHeadLength", LENGTH),
        ("BodyDia", BODY_DIA),
        ("UnderHeadCornerR", UNDERHEAD_CORNER_R),
        ("TipChamfer", TIP_CHAMFER),
        ("PlainLength", PLAIN_LENGTH_MIN),
        ("FullThread", FULL_THREAD_STATION_MAX),
        ("SlotWidth", SLOT_WIDTH),
        ("SlotDepth", SLOT_DEPTH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Head revolve on the Right plane: sketch (u, v) maps to model (-Z, Y), so
    # the head (+Z) lies at negative u, the flat top at u = -HEAD_H.  The
    # relief chamfer cuts the under-face's outer corner (u = 0, v = HEAD_R).
    head = SketchDims()
    u_top = -HEAD_H
    relief = HEAD_RELIEF_CHAMFER
    check("create_sketch head profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    try:
        axis = check(
            "head axis centerline",
            await adapter.add_centerline(u_top, 0.0, 0.0, 0.0),
        )
        head_seat, head_relief, head_side, head_top, head_close = await add_line_chain(
            adapter,
            [
                (0.0, 0.0),
                (0.0, HEAD_R - relief),
                (-relief, HEAD_R),
                (u_top, HEAD_R),
                (u_top, 0.0),
            ],
            close=True,
        )
    finally:
        # Session state on the seat: a failed segment must not leave sketch
        # inference off for the next leaf.
        set_sketch_direct_db(adapter, False)
    for line, relation in (
        (head_seat, "vertical"),
        (head_side, "horizontal"),
        (head_top, "vertical"),
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
    await add_diametric_linear_dimension(
        adapter, axis, head_side, (u_top / 2.0, HEAD_R + 4.0), "HeadDia"
    )
    head.record("HeadDia", '"HeadDia"')
    # The relief's axial leg is the printed size; its radial leg equals it by
    # equation: 45 degrees (the tip chamfer's recipe).
    await dimension_between(
        adapter,
        f"{head_relief}.start",
        f"{head_relief}.end",
        "horizontal_distance",
        relief,
        "head relief chamfer",
    )
    head.record("HeadReliefChamfer", '"HeadReliefChamfer"')
    await dimension_between(
        adapter,
        f"{head_relief}.start",
        f"{head_relief}.end",
        "vertical_distance",
        relief,
        "head relief chamfer rise",
    )
    head.record("HeadReliefChamferRise", '"HeadReliefChamfer"')
    await ensure_fully_defined(adapter, "head profile sketch")
    check("exit_sketch head profile", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    check("revolve head", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Head")
    await _volume_check(
        adapter, "flat-topped cheese head with relief chamfer", V_HEAD, 0.005 * V_HEAD
    )

    # Shank revolve on the Right plane, toward +u (model -Z).  The body runs
    # flat from the under-head corner's round to the tip chamfer.  The round
    # is the profile's own concave quarter-circle, tangent to the head face
    # and the body (build_pd_transgear_knob_shaft's neck corners), so its
    # radius is a sketch dimension on the profile's side of the axis: the
    # drawing's radius lands on the side view's upper corner.
    shank = SketchDims()
    check("create_sketch shank profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    try:
        shank_axis = check(
            "shank axis centerline",
            await adapter.add_centerline(0.0, 0.0, LENGTH, 0.0),
        )
        (face,) = await add_line_chain(
            adapter, [(0.0, 0.0), CORNER_FACE_TANGENT], close=False
        )
        corner = check(
            "under-head corner arc",
            await adapter.add_arc(
                *CORNER_CENTER, *CORNER_FACE_TANGENT, *CORNER_BODY_TANGENT
            ),
        )
        points = [
            CORNER_BODY_TANGENT,
            (LENGTH - TIP_CHAMFER, BODY_R),
            (LENGTH, BODY_R - TIP_CHAMFER),
            (LENGTH, 0.0),
            (0.0, 0.0),
        ]
        lines = await add_line_chain(adapter, points, close=False)
    finally:
        # Session state on the seat (as the head profile above).
        set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        (u0, v0), (u1, v1) = points[index], points[index + 1]
        if u0 != u1 and v0 != v1:
            continue  # the tip chamfer: dimensioned below
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"shank profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        f"shank profile vertical {face}",
        await adapter.add_sketch_constraint(face, None, "vertical"),
    )
    body, tip_chamfer = lines[0], lines[1]
    for first, second in ((face, corner), (corner, body)):
        check(
            f"under-head corner tangent {first} {second}",
            await adapter.add_sketch_constraint(first, second, "tangent"),
        )
    # Every axial size reads from the under-head face, the clamp face.
    for name, start, end, value in (
        ("UnderHeadLength", f"{face}.end", f"{tip_chamfer}.end", LENGTH),
        ("TipChamfer", f"{tip_chamfer}.start", f"{tip_chamfer}.end", TIP_CHAMFER),
    ):
        await dimension_between(
            adapter, start, end, "horizontal_distance", value, f"shank {name}"
        )
        shank.record(name, f'"{name}"')
    # The tip chamfer's rise equals its axial leg by equation: 45 degrees.
    await dimension_between(
        adapter,
        f"{tip_chamfer}.start",
        f"{tip_chamfer}.end",
        "vertical_distance",
        TIP_CHAMFER,
        "shank TipChamfer rise",
    )
    shank.record("TipChamferRise", '"TipChamfer"')
    await add_diametric_linear_dimension(
        adapter,
        shank_axis,
        body,
        ((UNDERHEAD_CORNER_R + LENGTH - TIP_CHAMFER) / 2.0, BODY_R + 4.0),
        "BodyDia",
    )
    shank.record("BodyDia", '"BodyDia"')
    check(
        "under-head corner radius",
        await adapter.add_sketch_dimension(corner, None, "radial", UNDERHEAD_CORNER_R),
    )
    shank.record("UnderHeadCornerR", '"UnderHeadCornerR"')
    await anchor_point_to_origin(
        adapter, f"{face}.start", 0.0, 0.0, "shank under-head centre"
    )
    await ensure_fully_defined(adapter, "shank profile sketch")
    check("exit_sketch shank profile", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank.apply(adapter, "ShankProfile")
    check("revolve shank", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Shank")
    await _volume_check(
        adapter,
        "turned cheese-head screw with corner round and tip chamfer",
        V_TURNED,
        0.005 * V_TURNED,
    )

    # Driver slot across the flat top: sketched on a plane at the top face and
    # cut down into the head (a cut runs against the plane normal by default).
    check(
        "create_plane SlotPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=HEAD_H
            )
        ),
    )
    name_last_feature(adapter, "SlotPlane")
    plane_dim = name_dimensions(adapter, "SlotPlane", ["TopStation"])
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
    await _volume_check(adapter, "slotted cheese-head screw", V_FINAL, 0.02 * V_SLOT)
    blank_reference_geometry(adapter, (("SlotPlane", "PLANE"),))

    # Drawing-only station reference.  The top-to-tip overall, printed as a
    # reference for stock cut-off: one construction line on the axis of the
    # Right plane whose single length dimension IS the printed value (policy
    # drawing-simplicity-policy.md `How the repository implements the
    # guidelines`), driven by the same globals so no geometry moves.  The
    # plain length's MIN and the full-thread station's MAX: the under-head
    # face to each body-silhouette witness at its printed limit, between the
    # witnesses' start points.
    stations = SketchDims()
    check("create_sketch station reference", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    try:
        overall_line = check(
            "overall reference line",
            await adapter.add_line(u_top, 0.0, LENGTH, 0.0),
        )
        (fu0, fv0), (fu1, fv1) = FACE_WITNESS_LINE
        face_witness = check(
            "under-head face witness",
            await adapter.add_line(fu0, fv0, fu1, fv1),
        )
        (pu0, pv0), (pu1, pv1) = PLAIN_WITNESS_LINE
        plain_witness = check(
            "plain-length witness",
            await adapter.add_line(pu0, pv0, pu1, pv1),
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
        (plain_witness, "horizontal"),
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
        adapter, f"{overall_line}.start", u_top, 0.0, "overall reference top"
    )
    stations.record("TopReference", '"HeadHeight"')
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
        adapter, f"{face_witness}.start", fu0, fv0, "face witness at corner tangent"
    )
    stations.record("FaceWitnessRadius", '"BodyDia" / 2 + "UnderHeadCornerR"')
    await dimension_between(
        adapter,
        f"{face_witness}.start",
        f"{face_witness}.end",
        "vertical_distance",
        STATION_WITNESS,
        "face witness length",
    )
    stations.record("FaceWitness")
    # Each printed station runs face to body silhouette; the face witness
    # stands the corner round's radius above the body.
    for name, witness, (u0, v0) in (
        ("PlainLength", plain_witness, (pu0, pv0)),
        ("FullThread", thread_witness, (tu0, tv0)),
    ):
        await anchor_point_to_point(
            adapter,
            f"{face_witness}.start",
            f"{witness}.start",
            u0 - fu0,
            v0 - fv0,
            f"{name} station",
        )
        stations.record(name, f'"{name}"')
        stations.record(f"{name}Drop", '"UnderHeadCornerR"')
        await dimension_between(
            adapter,
            f"{witness}.start",
            f"{witness}.end",
            "horizontal_distance",
            STATION_WITNESS,
            f"{name} witness length",
        )
        stations.record(f"{name}Witness")
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
    driven = await _volume_check(
        adapter,
        "driven slotted cheese-head screw (equations neutral)",
        V_FINAL,
        0.02 * V_SLOT,
    )

    # Cosmetic 1/4-28 from the tip chamfer's major-diameter edge back to the
    # full-thread station's MAX, so the side view draws the thread's minor
    # lines (ASME Y14.6 simplified) and the shaded isometric shows the thread
    # the callout names (build_mg_magnifying_vertical_rod).  It cuts nothing;
    # the calibrated sizes (springs.yaml upper_support) are untouched.
    adapter._zoom_to_fit(adapter.currentModel)
    check(
        f"cosmetic thread {THREAD}",
        await adapter.add_thread(
            AddThreadParameters(
                edge_point=list(THREAD_EDGE_POINT),
                standard="ansi_inch",
                size=THREAD_SIZE,
                end_type="blind",
                depth=COSMETIC_THREAD_DEPTH,
            )
        ),
    )
    await _volume_check(adapter, "cosmetic thread cuts nothing", driven, 1e-6)
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"spring screw: expected one solid body, found {len(bodies)}"
        )

    # Model-owned limits (drawing-simplicity-policy.md `How the repository
    # implements the guidelines`), owner rulings 2026-10-27 (#1951), printed
    # in inches (#290, sm_gooseneck_spring_screw_spec.PRINTED_BANDS): the body
    # Ø as the LIMIT band .248/.245, the thread blank inside the 1/4-28
    # UNF-2A major band; the plain length as the single ".14 MIN" from the
    # under-head face, so the loop always bears on the plain body; the
    # full-thread station as the single ".225 MAX", so the end piece's
    # counterbore clears the run-out; the head Ø and its relief chamfer as the
    # LIMIT bands .456/.449 and .059/.056, so the loop's transition wire clears
    # the head and the flat inside the relief still bears the loop.  Every
    # other mark takes the title block's band.
    for feature, name, model, tol_type in (
        ("ShankProfile", "BodyDia", BODY_DIA, BODY_DIA_TOL_TYPE),
        ("HeadProfile", "HeadDia", HEAD_DIA, HEAD_DIA_TOL_TYPE),
        (
            "HeadProfile",
            "HeadReliefChamfer",
            HEAD_RELIEF_CHAMFER,
            HEAD_RELIEF_CHAMFER_TOL_TYPE,
        ),
    ):
        _limit_band(adapter, feature, name, model, PRINTED_BANDS[name], tol_type)
    # The under-head corner's R.020 MAX (codjiflo round 4 on #1997): the
    # modelled radius is the limit, the band runs from sharp up to it.
    set_single_limit(
        adapter,
        "ShankProfile",
        "UnderHeadCornerR",
        limit=UNDERHEAD_CORNER_R,
        band=UNDERHEAD_CORNER_R_BAND,
        tol_type=UNDERHEAD_CORNER_R_TOL_TYPE,
    )
    set_single_limit(
        adapter,
        "StationReference",
        "PlainLength",
        limit=PLAIN_LENGTH_MIN,
        band=PLAIN_LENGTH_MIN_BAND,
        tol_type=PLAIN_LENGTH_MIN_TOL_TYPE,
    )
    set_single_limit(
        adapter,
        "StationReference",
        "FullThread",
        limit=FULL_THREAD_STATION_MAX,
        band=FULL_THREAD_STATION_MAX_BAND,
        tol_type=FULL_THREAD_STATION_MAX_TOL_TYPE,
    )

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
