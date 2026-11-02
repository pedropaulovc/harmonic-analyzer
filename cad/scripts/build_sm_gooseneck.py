r"""Build MHA-SM-01, the gooseneck: a bent 1/2 in tube with a brazed end piece.

Owner rulings 2026-10-27 (#1951): the whole gooseneck is 1/2 in x 0.065 in
4130-N seamless tube, bent R3.0 (the 1/2 in x 3 in CLR die).  Its arm ends
flush, with no step, in a SOLID Ø.500 end piece silver-brazed on a shank
inside the tube bore and tapped 1/4-28 UNF-2B BLIND for the MHA-SM-04 spring
screw; an arm-end counterbore clears that screw's die run-out
(``sm_gooseneck_spring_joint``).  A 5/8 in x 0.058 in 4130-N sleeve,
select-fitted from stock and brazed, covers the leg from its foot: the post
the east top-frame hub's Ø17 bore and set screw take.  The made MHA-SM-04
screw is a separate component, not part of this weldment.  Decimal-inch
document and sheet (#290, the registry row's drawing_unit).

One weldment part of two solid bodies, the tube (its sleeve merged on) and
the end piece, so a section hatches each as its own part and every view
draws their joint (machinist review of 3c0b5d87c), built in this order:

1. ``Leg``: the tube from its foot LEG_BOTTOM up to the bend tangent LEG_TOP.
2. ``BendArmSweep``: the 90-degree bend R BEND_R and the TUBE_STRAIGHT arm to
   TUBE_END_X along ``BendPath``, hollow, merged onto the leg.
3. ``EndPiece``: the solid head Ø PLUG_DIA from the end face ARM_END_X to the
   tube end TUBE_END_X, then the braze shank Ø PLUG_SHANK_DIA x
   PLUG_SHANK_LENGTH into the tube bore -- one revolve on ``ArmAxisPlane``
   (the horizontal plane through the arm axis, so section A-A on the print
   carries its dimensions), NOT merged: its head bears on the tube end and
   its shank stands in the bore at the joint's nominal braze clearance.
4. ``Counterbore``: a revolved cut Ø COUNTERBORE_DIA x COUNTERBORE_DEPTH
   from the end face, its floor corner round at its printed R.004 MAX; its
   Ø and depth carry native LIMIT bands.  Then ``ThreadBore``: the native blind
   bottoming tap from ``TAP_SPEC``, started on the counterbore floor, both
   depths from it.  ``SpringScrewAxis`` is their hidden, equation-driven
   assembly reference.
5. ``Sleeve``: Ø SLEEVE_DIA from LEG_BOTTOM to SLEEVE_TOP, its bore the tube
   OD, revolved onto the leg.
6. ``StationReference``: a hidden construction sketch on the Front plane
   whose two lines lie on the leg and arm axes; its dimensions are the
   elevation's leg length and arm straight.
7. ``OverallReference``: a hidden construction sketch on the Front plane
   whose lines lie on the foot face, the bare leg's outer silhouette and the
   arm's top silhouette; its dimensions are the elevation's reference overall
   height and reach.

Layout (mm): origin at the leg's reference mid-height; leg y -329.46..87.1,
bend centre (-76.2, 87.1), arm axis y 163.3, end face x ARM_END_X.

Run on a SolidWorks worker::

    uv run python cad\scripts\build_sm_gooseneck.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import (
    _named_dimension,
    _named_dimensions,
    apply_drawing_precision,
)
from _drawing_prefix import set_dimension_prefix
from _drawing_tolerances import _set_tolerance_precision
from _extrude import extrude_at_offset
from _feature_tree import name_last_feature
from _holes import blind_hole_volume_mm3, wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
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
from _sketch_circle import define_circle
from _single_limit_tolerance import set_single_limit
from _visibility import blank_reference_geometry
from sm_gooseneck_spec import (
    DIMENSION_CALLOUTS,
    DIMENSION_CALLOUTS_ABOVE,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRAWING_PRECISION_BY_NAME,
    ELEVATION_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
    REFERENCE_DIMENSIONS,
    TUBE_OD_REF_SPAN,
    TUBE_OD_REF_Y,
    UNIT,
)

# The form nominals live in sm_gooseneck_geom -- the prose-free module the
# summing assembly imports for its hang proof -- so this build and that proof
# can never drift apart.
from sm_gooseneck_geom import (
    ARM_END_X,
    ARM_STRAIGHT,
    ARM_Y,
    BEND_R,
    LEG_BOTTOM,
    LEG_TOP,
    PLUG_DIA,
    PLUG_HEAD_LENGTH,
    PLUG_SHANK_LENGTH,
    SLEEVE_DIA,
    SLEEVE_LENGTH,
    SLEEVE_TOP,
    TUBE_BORE_DIA,
    TUBE_DIA,
    TUBE_END_X,
    TUBE_STRAIGHT,
    WALL_T,
)
from sm_gooseneck_spring_joint import (
    COUNTERBORE_DEPTH,
    COUNTERBORE_DEPTH_MAX,
    COUNTERBORE_DEPTH_MIN,
    COUNTERBORE_DIA,
    COUNTERBORE_DIA_MAX,
    COUNTERBORE_DIA_MIN,
    COUNTERBORE_FLOOR_CORNER_R_BAND,
    COUNTERBORE_FLOOR_CORNER_R_MAX,
    COUNTERBORE_FLOOR_CORNER_R_TOL_TYPE,
    PLUG_SHANK_DIA,
    TAP_DRILL_DEPTH_FROM_FLOOR,
    TAP_DRILL_DIA,
    TAP_SPEC,
)

PART_NAME = "sm-gooseneck"
# The registry row names 4130-N tube and an AISI 1018 end piece; SolidWorks'
# plain carbon steel stands in for their density.
MATERIAL = "Plain Carbon Steel"

TUBE_R = TUBE_DIA / 2.0
TUBE_IR = TUBE_BORE_DIA / 2.0
RING_AREA = math.pi * (TUBE_R**2 - TUBE_IR**2)  # the tube wall's cross-section
PLUG_R = PLUG_DIA / 2.0
SHANK_R = PLUG_SHANK_DIA / 2.0
# The shank's inner end, inside the straight tube short of the bend.
SHANK_END_X = TUBE_END_X + PLUG_SHANK_LENGTH
COUNTERBORE_R = COUNTERBORE_DIA / 2.0
COUNTERBORE_FLOOR_X = ARM_END_X + COUNTERBORE_DEPTH
# The floor corner's round (ArmAxisPlane sketch u along the arm, v radial):
# its tangent points on the floor and on the wall, the quarter CCW between.
_CB_CORNER_R = COUNTERBORE_FLOOR_CORNER_R_MAX
COUNTERBORE_CORNER_CENTER = (
    COUNTERBORE_FLOOR_X - _CB_CORNER_R,
    COUNTERBORE_R - _CB_CORNER_R,
)
COUNTERBORE_CORNER_FLOOR_TANGENT = (COUNTERBORE_FLOOR_X, COUNTERBORE_R - _CB_CORNER_R)
COUNTERBORE_CORNER_WALL_TANGENT = (COUNTERBORE_FLOOR_X - _CB_CORNER_R, COUNTERBORE_R)
TAP_DRILL_R = TAP_DRILL_DIA / 2.0
SLEEVE_R = SLEEVE_DIA / 2.0
_SW_TOL_LIMIT = 3  # swTolType_e.swTolLIMIT

if not math.isclose(PLUG_DIA, TUBE_DIA, abs_tol=1e-9):
    raise AssertionError("gooseneck end piece is not flush with the tube OD")
if not TAP_DRILL_R < SHANK_R < TUBE_IR:
    raise AssertionError("gooseneck braze shank does not sit clear in the tube bore")
if SHANK_END_X >= -BEND_R:
    raise AssertionError("gooseneck braze shank reaches past the bend tangent")
if not TAP_DRILL_R < COUNTERBORE_R < PLUG_R:
    raise AssertionError("gooseneck counterbore does not sit between tap and OD")
if not math.isclose(TUBE_END_X - ARM_END_X, PLUG_HEAD_LENGTH, abs_tol=1e-9):
    raise AssertionError("gooseneck tube does not end on the end piece's head")

# Analytic volumes, mm^3.
V_END_PIECE = math.pi * (PLUG_R**2 * PLUG_HEAD_LENGTH + SHANK_R**2 * PLUG_SHANK_LENGTH)
# The cut less the floor corner's round, the spandrel (1 - pi/4) r^2 revolved
# about its centroid's radius (Pappus).
_CB_CORNER_SPANDREL = (1.0 - math.pi / 4.0) * _CB_CORNER_R**2
_CB_CORNER_CENTROID_R = (
    COUNTERBORE_R - (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi) * _CB_CORNER_R
)
V_COUNTERBORE = (
    math.pi * COUNTERBORE_R**2 * COUNTERBORE_DEPTH
    - 2.0 * math.pi * _CB_CORNER_CENTROID_R * _CB_CORNER_SPANDREL
)
V_TAP = blind_hole_volume_mm3(TAP_DRILL_DIA, TAP_DRILL_DEPTH_FROM_FLOOR)
V_LEG = RING_AREA * (LEG_TOP - LEG_BOTTOM)
# Quarter torus with an annular cross-section (Pappus): (pi/2) * BendR * ring.
V_BEND = math.pi / 2.0 * BEND_R * RING_AREA
V_ARM = RING_AREA * TUBE_STRAIGHT
V_SLEEVE = math.pi * (SLEEVE_R**2 - TUBE_R**2) * SLEEVE_LENGTH
V_FINAL = V_END_PIECE - V_TAP - V_COUNTERBORE + V_LEG + V_BEND + V_ARM + V_SLEEVE


def _finite(label: str, volume: float) -> float:
    # NaN passes every |vol - expected| > tol comparison (the shared
    # volume_check's included), so a non-finite read stops the build
    # (codjiflo rounds 5 and 6 on #1997).
    if not math.isfinite(volume):
        raise RuntimeError(f"{label}: non-finite volume {volume!r}")
    return volume


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    if not res.is_success:
        raise RuntimeError(f"mass properties: {res.error}")
    return _finite("volume", float(res.data.volume))


async def _volume_check(adapter, label: str, expected: float, tol: float) -> float:
    return _finite(label, await volume_check(adapter, label, expected, tol))


def _construction(adapter, line: str, label: str) -> None:
    """Flag one sketch line as construction geometry and read it back."""
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{label} {line} did not take the construction flag")


@_telemetry.traced("part.limit_band", label_param="name")
def _limit_band(
    adapter, feature: str, name: str, model: float, limits: tuple[float, float]
) -> None:
    """A dimension as a native LIMIT band: SOLIDWORKS prints the upper and
    lower limits, the model value plus each deviation, at the dimension's
    own places (build_sm_gooseneck_spring_screw._limit_band).  #290: the
    calibrated mm model is off the inch grid, so the deviations are not; the
    printed ``limits`` (mm, lower and upper) are, and they set the places.
    The deviations come from the spec's ``model``, never the read-back
    SystemValue, whose inch-document float noise would need more than eight
    places."""
    label = f"{name}@{feature}"
    display, dimension = _named_dimension(adapter, feature, name)
    value = float(dimension.SystemValue) * 1000.0
    if not math.isclose(value, model, abs_tol=1e-6):
        raise RuntimeError(f"{label}: nominal {value!r} mm is not the spec's {model!r}")
    lower, upper = (limit - model for limit in limits)  # native API order, mm
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = _SW_TOL_LIMIT
    if tolerance.SetValues(lower / 1000.0, upper / 1000.0) is not True:
        raise RuntimeError(f"{label}: LIMIT deviations were rejected")
    if (
        int(tolerance.Type) != _SW_TOL_LIMIT
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
        limits,
        display_unit=UNIT,
        label=label,
        places=DRAWING_PRECISION_BY_NAME[name],
    )
    _telemetry.success(
        f"{label}: LIMIT {limits[1] / 25.4:.{places}f}/{limits[0] / 25.4:.{places}f} in"
    )


@_telemetry.traced("part.dimension_callouts")
def _author_dimension_callouts(adapter) -> None:
    """Persist each printed callout on its source dimension, below or above
    the value (build_sm_gooseneck_spring_screw._author_dimension_callouts):
    the drawing imports and reads them back, never writing them itself."""
    # swDimensionTextCalloutBelow = 4, swDimensionTextCalloutAbove = 3.
    for slot, by_feature in ((4, DIMENSION_CALLOUTS), (3, DIMENSION_CALLOUTS_ABOVE)):
        for feature, callouts in by_feature.items():
            resolved = _named_dimensions(adapter, feature, set(callouts))
            for name, text in callouts.items():
                display, _dimension = resolved[name]
                display.SetText(slot, text)
                if str(display.GetText(slot) or "").replace("\r\n", "\n") != text:
                    raise RuntimeError(f"{name}@{feature}: callout did not persist")


@_telemetry.traced("part.reference_dimensions")
def _author_reference_dimensions(adapter) -> None:
    """Parenthesize the stock Ø on their source dimensions: as supplied, they
    print as reference, untoleranced (the drawing imports them as they are)."""
    for feature, names in REFERENCE_DIMENSIONS.items():
        resolved = _named_dimensions(adapter, feature, set(names))
        for name in names:
            display, _dimension = resolved[name]
            display.ShowParenthesis = True
            if not bool(display.ShowParenthesis):
                raise RuntimeError(
                    f"{name}@{feature}: reference parentheses did not persist"
                )


async def _tube_od_reference(adapter) -> list[tuple[str, str]]:
    """The tube's stock Ø on the elevation, as a reference: a hidden Front-plane
    sketch whose line runs along the bare leg's right silhouette,
    TUBE_OD_REF_SPAN about mid-way between the sleeve's top and the bend's entry
    tangent, Ø-dimensioned from a centreline on the leg axis.  Returns the
    deferred drive jobs."""
    y0 = TUBE_OD_REF_Y - TUBE_OD_REF_SPAN / 2.0
    y1 = TUBE_OD_REF_Y + TUBE_OD_REF_SPAN / 2.0
    dims = SketchDims()
    check("create_sketch tube OD reference", await adapter.create_sketch("Front"))
    # Direct-to-DB: the lines lie on the leg's axis and silhouette, which
    # creation-time inference would relate to the model's edges.
    set_sketch_direct_db(adapter, True)
    try:
        axis = check(
            "tube OD reference axis",
            await adapter.add_centerline(0.0, y0, 0.0, y1),
        )
        edge = check(
            "tube OD reference line",
            await adapter.add_line(TUBE_DIA / 2.0, y0, TUBE_DIA / 2.0, y1),
        )
    finally:
        set_sketch_direct_db(adapter, False)
    for line in (axis, edge):
        check(
            f"tube OD reference vertical {line}",
            await adapter.add_sketch_constraint(line, None, "vertical"),
        )
    for end in ("start", "end"):
        check(
            f"tube OD reference {end} level",
            await adapter.add_sketch_constraint(
                f"{axis}.{end}", f"{edge}.{end}", "horizontal_points"
            ),
        )
    await anchor_point_to_origin(adapter, f"{axis}.start", 0.0, y0, "tube OD reference")
    dims.record("TubeOdRefStation")
    await dimension_between(
        adapter,
        f"{axis}.start",
        f"{axis}.end",
        "vertical_distance",
        TUBE_OD_REF_SPAN,
        "tube OD reference span",
    )
    dims.record("TubeOdRefSpan")
    # The outline stays a solid line: SolidWorks makes a centreline-to-
    # construction-line dimension plain linear, not diametric (farm run
    # 20261031T205208603Z).  The sketch feeds no feature and is blanked.
    await add_diametric_linear_dimension(
        adapter, axis, edge, (TUBE_DIA / 2.0 + 4.0, TUBE_OD_REF_Y), "TubeOdRef"
    )
    dims.record("TubeOdRef", '"TubeDia"')
    await ensure_fully_defined(adapter, "tube OD reference sketch")
    check("exit_sketch tube OD reference", await adapter.exit_sketch())
    name_last_feature(adapter, "TubeOdReference")
    return dims.apply(adapter, "TubeOdReference")


# OverallReference's witness stubs: this long (1 mm on the 1:3 sheet), each on
# a drawn edge and ending at the witness point, so the edge's own ink covers
# the phantom.  A full-length arm line over the end piece's top outline read
# as a stray dashed line (machinist review r8, farm run 20261101T035809796Z).
_OVERALL_STUB = 3.0


async def _overall_reference(adapter) -> list[tuple[str, str]]:
    """The bent form's overall height and reach, as references: 417.1 and
    27.16 stop at the bend's tangents, so the finished part had no size to
    check from its faces (machinist review r5 of farm run
    20261101T004958072Z).  A hidden Front-plane sketch of four construction
    lines, each on a drawn edge: the foot face from the axis to the sleeve's
    outer corner, a stub of the bare leg's outer silhouette ending at the
    bend's entry tangent, and two stubs of the arm's top silhouette, one from
    the end face, one ending at the bend's exit tangent.  OverallHeight runs
    from the foot face to the arm's top, OverallReach from the end face to the
    leg's outer side.  Returns the deferred drive jobs."""
    top = ARM_Y + TUBE_DIA / 2.0
    leg_x = TUBE_DIA / 2.0
    dims = SketchDims()
    check("create_sketch overall reference", await adapter.create_sketch("Front"))
    # Direct-to-DB: the lines lie on the model's edges, which creation-time
    # inference would relate them to.
    set_sketch_direct_db(adapter, True)
    try:
        foot = check(
            "overall reference foot line",
            await adapter.add_line(0.0, LEG_BOTTOM, SLEEVE_DIA / 2.0, LEG_BOTTOM),
        )
        leg = check(
            "overall reference leg stub",
            await adapter.add_line(leg_x, LEG_TOP - _OVERALL_STUB, leg_x, LEG_TOP),
        )
        arm_end = check(
            "overall reference end-face stub",
            await adapter.add_line(ARM_END_X, top, ARM_END_X + _OVERALL_STUB, top),
        )
        arm_tangent = check(
            "overall reference arm tangent stub",
            await adapter.add_line(-BEND_R - _OVERALL_STUB, top, -BEND_R, top),
        )
    finally:
        set_sketch_direct_db(adapter, False)
    for line, relation in (
        (foot, "horizontal"),
        (leg, "vertical"),
        (arm_end, "horizontal"),
        (arm_tangent, "horizontal"),
    ):
        _construction(adapter, line, "overall reference")
        check(
            f"overall reference {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    await anchor_point_to_origin(
        adapter, f"{foot}.start", 0.0, LEG_BOTTOM, "overall reference foot centre"
    )
    dims.record("OverallFootStation", '-"LegBottom"')
    await dimension_between(
        adapter,
        f"{foot}.start",
        f"{foot}.end",
        "horizontal_distance",
        SLEEVE_DIA / 2.0,
        "overall reference foot line",
    )
    dims.record("OverallFootRadius", '"SleeveDia" / 2')
    await anchor_point_to_origin(
        adapter, f"{leg}.end", leg_x, LEG_TOP, "overall reference leg top"
    )
    dims.record("OverallLegX", '"TubeDia" / 2')
    dims.record("OverallLegTop", '"LegTop"')
    await dimension_between(
        adapter,
        f"{leg}.start",
        f"{leg}.end",
        "vertical_distance",
        _OVERALL_STUB,
        "overall reference leg stub",
    )
    dims.record("OverallLegStub")
    await dimension_between(
        adapter,
        f"{arm_tangent}.end",
        "origin",
        "horizontal_distance",
        BEND_R,
        "overall reference arm tangent",
    )
    dims.record("OverallArmTangentX", '"BendR"')
    for stub, name in (
        (arm_tangent, "OverallArmTangentStub"),
        (arm_end, "OverallArmEndStub"),
    ):
        await dimension_between(
            adapter,
            f"{stub}.start",
            f"{stub}.end",
            "horizontal_distance",
            _OVERALL_STUB,
            f"overall reference {name}",
        )
        dims.record(name)
    # Both arm stubs lie on the arm's top; the two printed dimensions fix
    # that height and the end face's station.
    check(
        "overall reference arm stubs level",
        await adapter.add_sketch_constraint(
            f"{arm_end}.start", f"{arm_tangent}.end", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{foot}.end",
        f"{arm_tangent}.end",
        "vertical_distance",
        top - LEG_BOTTOM,
        "overall height",
    )
    dims.record("OverallHeight", '"ArmY" + "TubeDia" / 2 - "LegBottom"')
    await dimension_between(
        adapter,
        f"{arm_end}.start",
        f"{leg}.end",
        "horizontal_distance",
        leg_x - ARM_END_X,
        "overall reach",
    )
    dims.record("OverallReach", '"TubeDia" / 2 - "ArmEndX"')
    await ensure_fully_defined(adapter, "overall reference sketch")
    check("exit_sketch overall reference", await adapter.exit_sketch())
    name_last_feature(adapter, "OverallReference")
    return dims.apply(adapter, "OverallReference")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        RevolveParameters,
        SweepParameters,
    )

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable form and end-piece globals drive the sketches below; the
    # native tap's thread identity comes from TAP_SPEC. The ``mm`` suffix is
    # load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units. Signed coordinates keep their sign in
    # the global; the UNSIGNED distance dims they drive negate them so the
    # equation evaluates positive. LegBottom is a feature parameter
    # (start-offset extrude) and the station sketches' foot.
    for name, value in (
        ("TubeDia", TUBE_DIA),
        ("WallT", WALL_T),
        ("LegTop", LEG_TOP),
        ("LegBottom", LEG_BOTTOM),
        ("BendR", BEND_R),
        ("ArmEndX", ARM_END_X),
        ("PlugHeadLength", PLUG_HEAD_LENGTH),
        ("PlugShankLength", PLUG_SHANK_LENGTH),
        ("PlugShankDia", PLUG_SHANK_DIA),
        ("CounterboreDia", COUNTERBORE_DIA),
        ("CounterboreDepth", COUNTERBORE_DEPTH),
        ("CounterboreFloorCornerR", COUNTERBORE_FLOOR_CORNER_R_MAX),
        ("SleeveDia", SLEEVE_DIA),
        ("SleeveTop", SLEEVE_TOP),
    ):
        await set_global(adapter, name, f"{value}mm")
    await set_global(adapter, "ArmY", '"LegTop" + "BendR"')
    await set_global(adapter, "ArmStraight", '-"ArmEndX" - "BendR"')
    # Flush, no step: the head is the tube's own diameter.
    await set_global(adapter, "PlugDia", '"TubeDia"')

    # Per-sketch dim names + drive equations are declared inline at each
    # record call; their drive jobs collect here and apply in one deferred
    # batch after the whole model + a rebuild exist (every equation target
    # must resolve).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Vertical leg (start-offset extrude from the Top plane: the leg is
    # asymmetric -- foot at LEG_BOTTOM, top at LEG_TOP into the bend). TWO
    # concentric on-axis circles -- the OD and the tube bore -- extrude as the
    # annular wall. Only the diameters are dims; the centre slots are ignored.
    leg = SketchDims()
    check("create_sketch leg", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        TUBE_R,
        "leg",
        dims=leg,
        names=("LegCx", "LegCz", "TubeDia"),
        drives=(None, None, '"TubeDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        TUBE_IR,
        "leg bore",
        dims=leg,
        names=("LegBoreCx", "LegBoreCz", "TubeBoreDia"),
        drives=(None, None, '"TubeDia" - 2 * "WallT"'),
    )
    await ensure_fully_defined(adapter, "leg sketch")
    check("exit_sketch leg", await adapter.exit_sketch())
    name_last_feature(adapter, "LegProfile")
    drive_jobs += leg.apply(adapter, "LegProfile")
    extrude_at_offset(adapter, LEG_TOP - LEG_BOTTOM, LEG_BOTTOM, merge_result=False)
    name_last_feature(adapter, "Leg")
    expected = V_LEG
    vol = await _volume(adapter)
    _telemetry.info(f"volume after leg: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"leg volume {vol:.1f} != {expected:.1f}")

    # 2. Quarter bend + straight arm to the tube end: ONE sweep along an arc +
    # line chain. Direct DB keeps inference relations off; exact-coordinate
    # joints still merge. add_arc draws CCW: bend entry (angle 0 from the
    # centre) to bend exit (angle 90).
    bend_path = SketchDims()
    check("create_sketch bend path", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    try:
        arc = check(
            "bend arc",
            await adapter.add_arc(
                -BEND_R,
                LEG_TOP,  # centre
                0.0,
                LEG_TOP,  # start (bend entry, top of the leg)
                -BEND_R,
                ARM_Y,  # end (bend exit into the arm)
            ),
        )
        arm = check(
            "tube arm",
            await adapter.add_line(-BEND_R, ARM_Y, TUBE_END_X, ARM_Y),
        )
    finally:
        # Session state on the seat: a failed segment must not leave sketch
        # inference off for the next leaf.
        set_sketch_direct_db(adapter, False)
    # Manual-dim sketch: record each display dim as it is created, in
    # creation order. The centre anchor at (-BEND_R, LEG_TOP) emits TWO
    # unsigned distance dims (horizontal then vertical), THEN the arc radius,
    # THEN the tube's straight arm -- four dims total.
    await anchor_point_to_origin(
        adapter, f"{arc}.center", -BEND_R, LEG_TOP, "bend centre"
    )
    bend_path.record("BendCentreX", '"BendR"')
    bend_path.record("BendCentreY", '"LegTop"')
    check(
        "bend radius",
        await adapter.add_sketch_dimension(arc, None, "radial", BEND_R),
    )
    bend_path.record("BendRadius", '"BendR"')
    check(
        "bend entry level with centre",
        await adapter.add_sketch_constraint(
            f"{arc}.start", f"{arc}.center", "horizontal_points"
        ),
    )
    check(
        "bend exit above centre",
        await adapter.add_sketch_constraint(
            f"{arc}.end", f"{arc}.center", "vertical_points"
        ),
    )
    check(
        "arm horizontal", await adapter.add_sketch_constraint(arm, None, "horizontal")
    )
    await dimension_between(
        adapter,
        f"{arm}.start",
        f"{arm}.end",
        "horizontal_distance",
        TUBE_STRAIGHT,
        "tube straight",
    )
    bend_path.record("TubeStraight", '"ArmStraight" - "PlugHeadLength"')
    await ensure_fully_defined(adapter, "bend path")
    check("exit_sketch bend path", await adapter.exit_sketch())
    # The sweep selects this sketch by name below; rename it BEFORE the sweep
    # so the path reference resolves to the new name. The path sketch is NOT
    # absorbed (it stays in the tree as the sweep path), so naming it here is
    # permanent.
    path_name = name_last_feature(adapter, "BendPath")
    drive_jobs += bend_path.apply(adapter, "BendPath")

    profile_plane = check(
        "create_plane bend profile",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=LEG_TOP)
        ),
    )
    # Both attempts' planes survive a failed first sweep, so hide them all.
    profile_planes = [getattr(profile_plane, "name", profile_plane)]
    check(
        "create_sketch bend profile",
        await adapter.create_sketch(profile_planes[-1]),
    )
    # Annular (OD + bore) like the leg, so the swept bend + arm stay hollow
    # tube -- and driven by the SAME TubeDia/WallT knobs as the leg. The drive
    # jobs are collected but only applied for whichever profile the sweep
    # actually consumed.
    bend_prof = SketchDims()
    await define_circle(
        adapter,
        0.0,
        0.0,
        TUBE_R,
        "bend profile",
        dims=bend_prof,
        names=("BendCx", "BendCz", "BendOD"),
        drives=(None, None, '"TubeDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        TUBE_IR,
        "bend profile bore",
        dims=bend_prof,
        names=("BendBoreCx", "BendBoreCz", "BendBoreDia"),
        drives=(None, None, '"TubeDia" - 2 * "WallT"'),
    )
    await ensure_fully_defined(adapter, "bend profile sketch")
    check("exit_sketch bend profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BendProfile")
    res = await adapter.create_sweep(SweepParameters(path=path_name))
    if res.is_success:
        drive_jobs += bend_prof.apply(adapter, "BendProfile")
    if not res.is_success:
        _telemetry.debug(f"bend sweep failed ({res.error}); flipping profile plane")
        profile_plane = check(
            "create_plane bend profile (flipped)",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Top Plane", offset=-LEG_TOP
                )
            ),
        )
        profile_planes.append(getattr(profile_plane, "name", profile_plane))
        check(
            "create_sketch bend profile (flipped)",
            await adapter.create_sketch(profile_planes[-1]),
        )
        bend_prof_flipped = SketchDims()
        await define_circle(
            adapter,
            0.0,
            0.0,
            TUBE_R,
            "bend profile (flipped)",
            dims=bend_prof_flipped,
            names=("BendCx", "BendCz", "BendOD"),
            drives=(None, None, '"TubeDia"'),
        )
        await define_circle(
            adapter,
            0.0,
            0.0,
            TUBE_IR,
            "bend profile bore (flipped)",
            dims=bend_prof_flipped,
            names=("BendBoreCx", "BendBoreCz", "BendBoreDia"),
            drives=(None, None, '"TubeDia" - 2 * "WallT"'),
        )
        await ensure_fully_defined(adapter, "bend profile sketch (flipped)")
        check("exit_sketch bend profile (flipped)", await adapter.exit_sketch())
        # Distinct name: if the primary sweep failed, the original
        # "BendProfile" sketch still exists (unconsumed), so reusing the name
        # would collide.
        name_last_feature(adapter, "BendProfileFlipped")
        res = await adapter.create_sweep(SweepParameters(path=path_name))
        if res.is_success:
            drive_jobs += bend_prof_flipped.apply(adapter, "BendProfileFlipped")
    check("sweep bend + arm", res)
    name_last_feature(adapter, "BendArmSweep")
    blank_reference_geometry(adapter, tuple((name, "PLANE") for name in profile_planes))
    # The sweep merges onto the leg; the end piece comes after, as its own
    # body.
    expected = expected + V_BEND + V_ARM
    vol = await _volume(adapter)
    _telemetry.info(
        f"volume after bend + arm: {vol:.1f} mm^3 (analytic {expected:.1f})"
    )
    # 0.02: the annular wall is a small share of the swept section, so the same
    # absolute B-rep slack is larger relative to the expectation.
    if abs(vol - expected) > 0.02 * expected:
        raise RuntimeError(f"bend volume {vol:.1f} != {expected:.1f}")

    # 3. The end piece, on the horizontal plane through the arm axis, as its
    # own body (see the module docstring).
    # Sketch (u, v) is model (x, -z) about the arm axis at v = 0.
    check(
        "create_plane ArmAxisPlane",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=ARM_Y)
        ),
    )
    name_last_feature(adapter, "ArmAxisPlane")
    drive_jobs.append(
        (name_dimensions(adapter, "ArmAxisPlane", ["ArmAxisStation"])[0], '"ArmY"')
    )
    end_piece = SketchDims()
    end_piece_points = [
        (SHANK_END_X, 0.0),
        (SHANK_END_X, SHANK_R),
        (TUBE_END_X, SHANK_R),
        (TUBE_END_X, PLUG_R),
        (ARM_END_X, PLUG_R),
        (ARM_END_X, 0.0),
    ]
    check("create_sketch end piece", await adapter.create_sketch("ArmAxisPlane"))
    set_sketch_direct_db(adapter, True)
    try:
        end_piece_axis = check(
            "end piece axis centerline",
            await adapter.add_centerline(ARM_END_X, 0.0, SHANK_END_X, 0.0),
        )
        end_piece_lines = await add_line_chain(adapter, end_piece_points)
    finally:
        # Session state on the seat: a failed segment must not leave sketch
        # inference off for the next leaf.
        set_sketch_direct_db(adapter, False)
    shank_end, shank_side, head_step, head_side, end_face, end_piece_floor = (
        end_piece_lines
    )
    for line, relation in (
        (shank_end, "vertical"),
        (shank_side, "horizontal"),
        (head_step, "vertical"),
        (head_side, "horizontal"),
        (end_face, "vertical"),
        (end_piece_floor, "horizontal"),
    ):
        check(
            f"end piece {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    await anchor_point_to_origin(
        adapter, f"{end_face}.end", ARM_END_X, 0.0, "end face centre"
    )
    end_piece.record("EndFaceStation", '-"ArmEndX"')
    for name, line, length in (
        ("PlugHeadLength", head_side, PLUG_HEAD_LENGTH),
        ("PlugShankLength", shank_side, PLUG_SHANK_LENGTH),
    ):
        await dimension_between(
            adapter,
            f"{line}.start",
            f"{line}.end",
            "horizontal_distance",
            length,
            f"end piece {name}",
        )
        end_piece.record(name, f'"{name}"')
    for name, line, u_mid, radius in (
        ("PlugDia", head_side, ARM_END_X + PLUG_HEAD_LENGTH / 2.0, PLUG_R),
        ("PlugShankDia", shank_side, TUBE_END_X + PLUG_SHANK_LENGTH / 2.0, SHANK_R),
    ):
        await add_diametric_linear_dimension(
            adapter, end_piece_axis, line, (u_mid, radius + 4.0), name
        )
        end_piece.record(name, f'"{name}"')
    await ensure_fully_defined(adapter, "end piece sketch")
    check("exit_sketch end piece", await adapter.exit_sketch())
    name_last_feature(adapter, "EndPieceProfile")
    drive_jobs += end_piece.apply(adapter, "EndPieceProfile")
    check(
        "revolve end piece",
        await adapter.create_revolve(
            RevolveParameters(angle=360.0, merge_result=False)
        ),
    )
    name_last_feature(adapter, "EndPiece")
    vol = await _volume_check(
        adapter, "solid end piece", vol + V_END_PIECE, 0.005 * V_END_PIECE
    )

    # 4. The arm-end counterbore: its flat floor sits past the screw's clamped
    # run-out, so the fat incomplete threads never reach the end piece's full
    # 2B thread.  The cutter's mouth lies on the end face, so its depth
    # dimension runs face to floor; the floor corner is modelled at its
    # printed limit, R.004 MAX, a native radial dimension (codjiflo P2 on
    # #1997).  It is cut FIRST: its floor is the tap's start face.
    counterbore = SketchDims()
    check("create_sketch counterbore", await adapter.create_sketch("ArmAxisPlane"))
    set_sketch_direct_db(adapter, True)
    try:
        counterbore_axis = check(
            "counterbore axis centerline",
            await adapter.add_centerline(ARM_END_X, 0.0, COUNTERBORE_FLOOR_X, 0.0),
        )
        (floor,) = await add_line_chain(
            adapter,
            [(COUNTERBORE_FLOOR_X, 0.0), COUNTERBORE_CORNER_FLOOR_TANGENT],
            close=False,
        )
        floor_corner = check(
            "counterbore floor corner arc",
            await adapter.add_arc(
                *COUNTERBORE_CORNER_CENTER,
                *COUNTERBORE_CORNER_FLOOR_TANGENT,
                *COUNTERBORE_CORNER_WALL_TANGENT,
            ),
        )
        wall, mouth, counterbore_floor_axis = await add_line_chain(
            adapter,
            [
                COUNTERBORE_CORNER_WALL_TANGENT,
                (ARM_END_X, COUNTERBORE_R),
                (ARM_END_X, 0.0),
                (COUNTERBORE_FLOOR_X, 0.0),
            ],
            close=False,
        )
    finally:
        # Session state on the seat (as the end piece above).
        set_sketch_direct_db(adapter, False)
    for line, relation in (
        (floor, "vertical"),
        (wall, "horizontal"),
        (mouth, "vertical"),
        (counterbore_floor_axis, "horizontal"),
    ):
        check(
            f"counterbore {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    for first, second in ((floor, floor_corner), (floor_corner, wall)):
        check(
            f"counterbore floor corner tangent {first} {second}",
            await adapter.add_sketch_constraint(first, second, "tangent"),
        )
    await anchor_point_to_origin(
        adapter, f"{mouth}.end", ARM_END_X, 0.0, "counterbore mouth centre"
    )
    counterbore.record("CounterboreFaceStation", '-"ArmEndX"')
    # Face to floor: from the mouth's rim to the floor's tangent point.
    await dimension_between(
        adapter,
        f"{mouth}.start",
        f"{floor}.end",
        "horizontal_distance",
        COUNTERBORE_DEPTH,
        "counterbore depth",
    )
    counterbore.record("CounterboreDepth", '"CounterboreDepth"')
    await add_diametric_linear_dimension(
        adapter,
        counterbore_axis,
        wall,
        (ARM_END_X + COUNTERBORE_DEPTH / 2.0, COUNTERBORE_R + 4.0),
        "CounterboreDia",
    )
    counterbore.record("CounterboreDia", '"CounterboreDia"')
    check(
        "counterbore floor corner radius",
        await adapter.add_sketch_dimension(
            floor_corner, None, "radial", COUNTERBORE_FLOOR_CORNER_R_MAX
        ),
    )
    counterbore.record("CounterboreFloorCornerR", '"CounterboreFloorCornerR"')
    await ensure_fully_defined(adapter, "counterbore sketch")
    check("exit_sketch counterbore", await adapter.exit_sketch())
    name_last_feature(adapter, "CounterboreProfile")
    drive_jobs += counterbore.apply(adapter, "CounterboreProfile")
    check(
        "revolve counterbore",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Counterbore")
    vol = await _volume_check(
        adapter, "arm-end counterbore", vol - V_COUNTERBORE, 0.02 * V_COUNTERBORE
    )

    # 4b. The native blind bottoming tap, started on the counterbore floor
    # (west-facing), both depths from that floor (sm_gooseneck_spring_joint).
    # If the wizard's table drill differs from TAP_DRILL_DIA, wizard_holes
    # fails loud (the joint's walls are budgeted on that drill).
    tap = wizard_holes(
        adapter,
        TAP_SPEC,
        [[COUNTERBORE_FLOOR_X, ARM_Y, 0.0]],
        (-1.0, 0.0, 0.0),
        f"gooseneck end piece ({TAP_SPEC.size} blind)",
        name="ThreadBore",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[((None, None), ("TapAxisY", '"ArmY"'))],
    )
    if abs(tap.depth_mm - TAP_DRILL_DEPTH_FROM_FLOOR) > 0.005:
        raise RuntimeError(
            f"gooseneck tap drill depth {tap.depth_mm:.3f} != "
            f"{TAP_DRILL_DEPTH_FROM_FLOOR:.3f} mm"
        )
    drive_jobs += tap.placement_drive_jobs
    vol = await _volume_check(adapter, "end piece blind tap", vol - V_TAP, 0.02 * V_TAP)
    blank_reference_geometry(adapter, (("ArmAxisPlane", "PLANE"),))

    await name_bore_axis(
        adapter,
        "Front Plane",
        0.0,
        "Top Plane",
        ARM_Y,
        "spring screw",
        drive_b='"ArmY"',
        drive_jobs=drive_jobs,
    )
    name_last_feature(adapter, "SpringScrewAxis")

    # 5. The sleeve over the leg from its foot, revolved about the leg axis
    # on the Front plane; its bore is the tube OD, so it merges onto the leg.
    sleeve = SketchDims()
    sleeve_points = [
        (TUBE_R, LEG_BOTTOM),
        (SLEEVE_R, LEG_BOTTOM),
        (SLEEVE_R, SLEEVE_TOP),
        (TUBE_R, SLEEVE_TOP),
    ]
    check("create_sketch sleeve", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    try:
        sleeve_axis = check(
            "sleeve axis centerline",
            await adapter.add_centerline(0.0, LEG_BOTTOM, 0.0, 0.0),
        )
        sleeve_lines = await add_line_chain(adapter, sleeve_points)
    finally:
        # Session state on the seat (as the end piece above).
        set_sketch_direct_db(adapter, False)
    sleeve_foot, sleeve_side, sleeve_top, sleeve_bore = sleeve_lines
    for line, relation in (
        (sleeve_axis, "vertical"),
        (sleeve_foot, "horizontal"),
        (sleeve_side, "vertical"),
        (sleeve_top, "horizontal"),
        (sleeve_bore, "vertical"),
    ):
        check(
            f"sleeve {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    await anchor_point_to_origin(adapter, f"{sleeve_axis}.end", 0.0, 0.0, "leg axis")
    check(
        "sleeve axis from the foot",
        await adapter.add_sketch_constraint(
            f"{sleeve_axis}.start", f"{sleeve_foot}.start", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{sleeve_foot}.start",
        "origin",
        "vertical_distance",
        -LEG_BOTTOM,
        "sleeve foot station",
    )
    sleeve.record("SleeveFootStation", '-"LegBottom"')
    await dimension_between(
        adapter,
        f"{sleeve_side}.start",
        f"{sleeve_side}.end",
        "vertical_distance",
        SLEEVE_LENGTH,
        "sleeve length",
    )
    sleeve.record("SleeveLength", '"SleeveTop" - "LegBottom"')
    for name, line, radius, drive in (
        ("SleeveDia", sleeve_side, SLEEVE_R, '"SleeveDia"'),
        ("SleeveBoreDia", sleeve_bore, TUBE_R, '"TubeDia"'),
    ):
        await add_diametric_linear_dimension(
            adapter,
            sleeve_axis,
            line,
            (radius + 4.0, (LEG_BOTTOM + SLEEVE_TOP) / 2.0),
            name,
        )
        sleeve.record(name, drive)
    await ensure_fully_defined(adapter, "sleeve sketch")
    check("exit_sketch sleeve", await adapter.exit_sketch())
    name_last_feature(adapter, "SleeveProfile")
    drive_jobs += sleeve.apply(adapter, "SleeveProfile")
    check(
        "revolve sleeve", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "Sleeve")
    # The sleeve adds only its own annulus: its bore is the leg's OD.
    final_vol = await _volume_check(
        adapter, "leg sleeve", vol + V_SLEEVE, 0.01 * V_SLEEVE
    )
    _telemetry.info(f"gooseneck volume {final_vol:.1f} mm^3 (analytic {V_FINAL:.1f})")
    if abs(final_vol - V_FINAL) > 0.02 * V_FINAL:
        raise RuntimeError(f"gooseneck volume {final_vol:.1f} != {V_FINAL:.1f}")

    # 6. Drawing-only station reference on the Front plane: two construction
    # lines on the leg and arm axes whose length dimensions ARE the printed
    # leg length (foot to the bend's entry tangent) and arm straight (the
    # bend's exit tangent to the end face), driven by the same globals so no
    # geometry moves.  Hidden at the end; the drawing shows it per view.
    stations = SketchDims()
    check("create_sketch station reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    try:
        leg_axis = check(
            "leg axis reference line",
            await adapter.add_line(0.0, LEG_BOTTOM, 0.0, LEG_TOP),
        )
        arm_axis = check(
            "arm axis reference line",
            await adapter.add_line(-BEND_R, ARM_Y, ARM_END_X, ARM_Y),
        )
    finally:
        # Session state on the seat (as the end piece above).
        set_sketch_direct_db(adapter, False)
    for line, relation in ((leg_axis, "vertical"), (arm_axis, "horizontal")):
        _construction(adapter, line, "station reference")
        check(
            f"station reference {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    await anchor_point_to_origin(
        adapter, f"{leg_axis}.start", 0.0, LEG_BOTTOM, "leg foot centre"
    )
    stations.record("LegFootStation", '-"LegBottom"')
    await dimension_between(
        adapter,
        f"{leg_axis}.start",
        f"{leg_axis}.end",
        "vertical_distance",
        LEG_TOP - LEG_BOTTOM,
        "leg length",
    )
    stations.record("LegLength", '"LegTop" - "LegBottom"')
    await anchor_point_to_origin(
        adapter, f"{arm_axis}.start", -BEND_R, ARM_Y, "arm bend tangent"
    )
    stations.record("ArmTangentX", '"BendR"')
    stations.record("ArmTangentY", '"ArmY"')
    await dimension_between(
        adapter,
        f"{arm_axis}.start",
        f"{arm_axis}.end",
        "horizontal_distance",
        ARM_STRAIGHT,
        "arm straight",
    )
    stations.record("ArmStraight", '"ArmStraight"')
    await ensure_fully_defined(adapter, "station reference sketch")
    check("exit_sketch station reference", await adapter.exit_sketch())
    name_last_feature(adapter, "StationReference")
    drive_jobs += stations.apply(adapter, "StationReference")
    drive_jobs += await _tube_od_reference(adapter)
    drive_jobs += await _overall_reference(adapter)

    # Apply the deferred drive equations now -- after the whole model + a
    # rebuild exists, so every target resolves. Each equation evaluates to the
    # value just built, so the geometry must not move; the re-check below is
    # the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await _volume_check(
        adapter, "driven gooseneck (equations neutral)", final_vol, 0.001 * final_vol
    )
    # Two bodies (module docstring): the tube with its sleeve merged on the
    # leg's OD, and the end piece, its head on the tube end's annulus.
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 2:
        raise RuntimeError(f"gooseneck: expected two solid bodies, found {len(bodies)}")

    # Model-owned limits: the counterbore depth prints as its LIMIT band from
    # the end face, .108/.112 (sm_gooseneck_spring_joint), the calibrated 2.78
    # model inside it; its Ø as LIMIT .279/.275 about the calibrated 7.00, the
    # lower limit the one the run-out clearance is budgeted on (codjiflo P1 on
    # #1997).
    _limit_band(
        adapter,
        "CounterboreProfile",
        "CounterboreDepth",
        COUNTERBORE_DEPTH,
        (COUNTERBORE_DEPTH_MIN, COUNTERBORE_DEPTH_MAX),
    )
    _limit_band(
        adapter,
        "CounterboreProfile",
        "CounterboreDia",
        COUNTERBORE_DIA,
        (COUNTERBORE_DIA_MIN, COUNTERBORE_DIA_MAX),
    )
    # The floor corner's R.004 MAX (codjiflo P1 round 5, P2 on #1997): the
    # modelled radius is the limit, the band runs from sharp up to it.
    set_single_limit(
        adapter,
        "CounterboreProfile",
        "CounterboreFloorCornerR",
        limit=COUNTERBORE_FLOOR_CORNER_R_MAX,
        band=COUNTERBORE_FLOOR_CORNER_R_BAND,
        tol_type=COUNTERBORE_FLOOR_CORNER_R_TOL_TYPE,
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _author_dimension_callouts(adapter)
    _author_reference_dimensions(adapter)
    # A sketch-only diametric dimension prints no Ø of its own (farm run
    # 20261031T233549214Z printed "(12.70)"); the revolve's sleeve Ø does.
    set_dimension_prefix(adapter, "TubeOdReference", "TubeOdRef", "<MOD-DIAM>")
    # The reference sketches own printed dimensions and only reference lines:
    # hide them so no assembly instance renders them (#880).  The drawing shows
    # them per view through _drawing_hidden_sketches to import those dimensions.
    blank_sketch(adapter, "StationReference")
    blank_sketch(adapter, "TubeOdReference")
    blank_sketch(adapter, "OverallReference")
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Elevation View Note": ELEVATION_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
