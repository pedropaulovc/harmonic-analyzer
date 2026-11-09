r"""Build MHA-SM-01, the gooseneck: a bent 1/2 in tube.

Owner rulings 2026-10-27 (#1951): the gooseneck is 1/2 in x 0.065 in 4130-N
seamless tube, bent R3.0 (the 1/2 in x 3 in CLR die).  Owner rulings
2026-11-08 (Pedro), #2315: MHA-SM-01 is the bent tube ALONE.  It is bent with
a tail, then its arm end is sawn and faced to TUBE_END_X; it is polished bare,
oiled or waxed, with no torch work.  The end plug that carries the shoulder
screw's tap is its own part, MHA-SM-05 ``sm-gooseneck-end-plug``, bonded into
the arm end at MHA-SM-00; the reference machine has no leg sleeve, so the
bare leg is the post MHA-FR-02's hub bore takes.  Decimal-inch document and
sheet (#290, the registry row's drawing_unit).

One part of one solid body, built in this order:

1. ``Leg``: the tube from its foot LEG_BOTTOM up to the bend tangent LEG_TOP.
2. ``BendArmSweep``: the 90-degree bend R BEND_R and the TUBE_STRAIGHT arm to
   the faced end TUBE_END_X along ``BendPath``, hollow, merged onto the leg.
3. ``StationReference``: a hidden construction sketch on the Front plane
   whose two lines lie on the leg and arm axes; its dimensions are the
   elevation's leg length and arm straight.
4. ``TubeOdReference``: a hidden Front-plane sketch carrying the tube's stock
   Ø across the bare leg.
5. ``OverallReference``: a hidden construction sketch on the Front plane
   whose lines lie on the foot face, the leg's outer silhouette and the arm's
   top silhouette; its dimensions are the elevation's overall height and
   reach.

Layout (mm): origin at the leg's reference mid-height; leg y -329.46..87.1,
bend centre (-76.2, 87.1), arm axis y 163.3, faced arm end x TUBE_END_X.

Run on a SolidWorks worker::

    uv run python cad\scripts\build_sm_gooseneck.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import (
    _named_dimensions,
    apply_drawing_precision,
)
from _extrude import extrude_at_offset
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from sm_gooseneck_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    REFERENCE_DIMENSIONS,
    TUBE_OD_REF_SPAN,
    TUBE_OD_REF_Y,
)

# The form nominals live in sm_gooseneck_geom -- the prose-free module the
# summing assembly imports for its hang proof -- so this build and that proof
# can never drift apart.
from sm_gooseneck_geom import (
    ARM_Y,
    BEND_R,
    LEG_BOTTOM,
    LEG_TOP,
    TUBE_BORE_DIA,
    TUBE_DIA,
    TUBE_END_X,
    TUBE_STRAIGHT,
    WALL_T,
)

PART_NAME = "sm-gooseneck"
# The registry row names 4130-N tube; SolidWorks' plain carbon steel stands in
# for its density.  The title block's material and finish come from the row
# (apply_drawing_properties).
MATERIAL = "Plain Carbon Steel"

TUBE_R = TUBE_DIA / 2.0
TUBE_IR = TUBE_BORE_DIA / 2.0
RING_AREA = math.pi * (TUBE_R**2 - TUBE_IR**2)  # the tube wall's cross-section

if not math.isclose(TUBE_STRAIGHT, -TUBE_END_X - BEND_R, abs_tol=1e-9):
    raise AssertionError("gooseneck arm straight does not end on the faced arm end")

# Analytic volumes, mm^3.
V_LEG = RING_AREA * (LEG_TOP - LEG_BOTTOM)
# Quarter torus with an annular cross-section (Pappus): (pi/2) * BendR * ring.
V_BEND = math.pi / 2.0 * BEND_R * RING_AREA
V_ARM = RING_AREA * TUBE_STRAIGHT
V_FINAL = V_LEG + V_BEND + V_ARM


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


@_telemetry.traced("part.dimension_callouts")
def _author_dimension_callouts(adapter) -> None:
    """Persist each printed callout below its source dimension: the drawing
    imports and reads them back, never writing them itself."""
    # swDimensionTextCalloutBelow = 4.
    for feature, callouts in DIMENSION_CALLOUTS.items():
        resolved = _named_dimensions(adapter, feature, set(callouts))
        for name, text in callouts.items():
            display, _dimension = resolved[name]
            display.SetText(4, text)
            if str(display.GetText(4) or "").replace("\r\n", "\n") != text:
                raise RuntimeError(f"{name}@{feature}: callout did not persist")


@_telemetry.traced("part.reference_dimensions")
def _author_reference_dimensions(adapter) -> None:
    """Parenthesize the reference dimensions on their sources: they print as
    reference, untoleranced (the drawing imports them as they are).

    ``ShowParenthesis`` brackets the whole text block, so a reference that
    carries a callout below (the tube's stock wall) would read its callout as
    reference too (machinist review of 6b67c9516).  That one brackets only its
    value with a "(" prefix and ")" suffix, carrying SolidWorks' own
    "<MOD-DIAM>" token since a custom prefix replaces the Ø glyph."""
    open_paren = "(<MOD-DIAM>"
    for feature, names in REFERENCE_DIMENSIONS.items():
        resolved = _named_dimensions(adapter, feature, set(names))
        for name in names:
            display, _dimension = resolved[name]
            if name in DIMENSION_CALLOUTS.get(feature, {}):
                display.SetText(1, open_paren)  # swDimensionTextPrefix
                display.SetText(2, ")")  # swDimensionTextSuffix
                if (str(display.GetText(1)), str(display.GetText(2))) != (
                    open_paren,
                    ")",
                ):
                    raise RuntimeError(
                        f"{name}@{feature}: reference brackets did not persist"
                    )
                continue
            display.ShowParenthesis = True
            if not bool(display.ShowParenthesis):
                raise RuntimeError(
                    f"{name}@{feature}: reference parentheses did not persist"
                )


async def _tube_od_reference(adapter) -> list[tuple[str, str]]:
    """The tube's stock Ø on the elevation, as a reference: a hidden Front-plane
    sketch whose line runs along the leg's right silhouette, TUBE_OD_REF_SPAN
    about TUBE_OD_REF_Y, Ø-dimensioned from a centreline on the leg axis.
    Returns the deferred drive jobs."""
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
# the phantom.  A full-length arm line over the arm's top outline read as a
# stray dashed line (machinist review r8, farm run 20261101T035809796Z).
_OVERALL_STUB = 3.0


async def _overall_reference(adapter) -> list[tuple[str, str]]:
    """The bent form's overall height and reach, to real faces: the leg
    length and arm straight stop at the bend's tangents, so the finished part
    had no size to check from its faces (machinist review r5 of farm run
    20261101T004958072Z).  A hidden Front-plane sketch of four construction
    lines, each on a drawn edge: the foot face from the axis to the leg's
    outer corner, a stub of the leg's outer silhouette ending at the bend's
    entry tangent, and two stubs of the arm's top silhouette, one from the
    faced arm end, one ending at the bend's exit tangent.  OverallHeight runs
    from the foot face to the arm's top, OverallReach from the faced arm end
    to the leg's outer side.  Returns the deferred drive jobs."""
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
            await adapter.add_line(0.0, LEG_BOTTOM, leg_x, LEG_BOTTOM),
        )
        leg = check(
            "overall reference leg stub",
            await adapter.add_line(leg_x, LEG_TOP - _OVERALL_STUB, leg_x, LEG_TOP),
        )
        arm_end = check(
            "overall reference arm-end stub",
            await adapter.add_line(TUBE_END_X, top, TUBE_END_X + _OVERALL_STUB, top),
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
        leg_x,
        "overall reference foot line",
    )
    dims.record("OverallFootRadius", '"TubeDia" / 2')
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
    # that height and the faced arm end's station.
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
        leg_x - TUBE_END_X,
        "overall reach",
    )
    dims.record("OverallReach", '"TubeDia" / 2 - "TubeEndX"')
    await ensure_fully_defined(adapter, "overall reference sketch")
    check("exit_sketch overall reference", await adapter.exit_sketch())
    name_last_feature(adapter, "OverallReference")
    return dims.apply(adapter, "OverallReference")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        SweepParameters,
    )

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable form globals drive the sketches below. The ``mm`` suffix is
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
        ("TubeEndX", TUBE_END_X),
    ):
        await set_global(adapter, name, f"{value}mm")
    await set_global(adapter, "ArmY", '"LegTop" + "BendR"')
    await set_global(adapter, "ArmStraight", '-"TubeEndX" - "BendR"')

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

    # 2. Quarter bend + straight arm to the faced arm end: ONE sweep along an
    # arc + line chain. Direct DB keeps inference relations off;
    # exact-coordinate joints still merge. add_arc draws CCW: bend entry
    # (angle 0 from the centre) to bend exit (angle 90).
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
    bend_path.record("TubeStraight", '"ArmStraight"')
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
    # The sweep merges onto the leg: the whole tube.
    # 0.02: the annular wall is a small share of the swept section, so the same
    # absolute B-rep slack is larger relative to the expectation.
    final_vol = await _volume_check(
        adapter, "bend + arm", V_FINAL, 0.02 * V_FINAL
    )
    _telemetry.info(f"gooseneck volume {final_vol:.1f} mm^3 (analytic {V_FINAL:.1f})")

    # 3. Drawing-only station reference on the Front plane: two construction
    # lines on the leg and arm axes whose length dimensions ARE the printed
    # leg length (foot to the bend's entry tangent) and arm straight (the
    # bend's exit tangent to the faced arm end), driven by the same globals so
    # no geometry moves.  Hidden at the end; the drawing shows it per view.
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
            await adapter.add_line(-BEND_R, ARM_Y, TUBE_END_X, ARM_Y),
        )
    finally:
        # Session state on the seat (as the bend path above).
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
        TUBE_STRAIGHT,
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
    # One body: the bent tube (the end plug is MHA-SM-05, its own part).
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(f"gooseneck: expected one solid body, found {len(bodies)}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _author_dimension_callouts(adapter)
    # The tube's stock Ø, a sketch-only diametric dimension, prints no Ø of
    # its own (farm run 20261031T233549214Z printed "(12.70)"); it carries
    # its wall callout, so _author_reference_dimensions writes its
    # "(<MOD-DIAM>" prefix.
    _author_reference_dimensions(adapter)
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
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
