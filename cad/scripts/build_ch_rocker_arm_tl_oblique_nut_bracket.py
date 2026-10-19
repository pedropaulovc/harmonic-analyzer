r"""Build the oblique-trammel jig's nut bracket (MHA-CH-06-TL-29; shop fixture).

An 18.5 x 48 x 35.3 block from 6061-T6 3/4 x 2 in flat, screwed to pivot
block 1's -Y face by two #8-32 SHCS; the leadscrew's flanged nut screws to
its -X face
(``ch_rocker_arm_tl_oblique_nut_bracket_spec``).

Layout (the spec's model frame, +Z up, the origin on the Y = 0 face at the
carriage centre): the block is a Top-plane rectangle (the Y = 0 face)
extruded -Y by the depth. The same sketch carries two reference points, the
#8 stations from the -X face's bottom corner: the origin's X is mid-air, so
the printed stations live there and the Hole Wizard placement dimensions stay
unprinted, driven from them. Then three native Hole Wizard features: the two
#8-32 taps blind from the Y = 0 face, the four #4-40 taps on the nut's
circle, and the nut seat (counterbore for the spigot over the screw's THRU
clearance), both on the -X face, placed from the Y = 0 face and the bottom.
The seat's placement dimensions print; the #4-40 taps' run from the edges, so
they stay unprinted and the taps print from the seat's axis on the hidden
Right-plane sketch ``NutPatternReference``.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_nut_bracket.py
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from typing import Any

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _holes import SharedCoordinate, blind_hole_volume_mm3, wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
)
from _sketch_chains import define_rectilinear_chain
from ch_rocker_arm_tl_oblique_nut_bracket_spec import (
    BLOCK_SCREW_POINTS,
    BLOCK_TAP_DRILL,
    BLOCK_TAP_DRILL_DEPTH,
    BLOCK_TAP_SPEC,
    BORE_Y,
    BORE_Z,
    BRACKET_DEPTH,
    BRACKET_FACE_X,
    BRACKET_HEIGHT,
    BRACKET_LENGTH,
    CALLOUT_PLACES,
    CBORE_BAND,
    CBORE_DEPTH,
    CBORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    DRAWING_VALUES,
    FACE_X,
    ISOMETRIC_VIEW_NOTE,
    NUT_HOLE_OFFSET,
    NUT_HOLE_POINTS,
    NUT_HOLE_Y,
    NUT_HOLE_Z,
    NUT_PATTERN_REFERENCE,
    NUT_SEAT_POINT,
    NUT_SEAT_SPEC,
    NUT_TAP_DRILL,
    NUT_TAP_DRILL_DEPTH,
    NUT_TAP_SPEC,
    REFERENCE_SKETCHES,
    SCREW_CLEARANCE_DIA,
    SCREW_X,
    SCREW_Z,
)

PART_NAME = "ch-rocker-arm-tl-oblique-nut-bracket"
MATERIAL = "6061 Alloy"  # the registry row names the 6061-T6 flat bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

V_BRACKET = BRACKET_LENGTH * BRACKET_DEPTH * BRACKET_HEIGHT
V_BLOCK_TAPS = len(BLOCK_SCREW_POINTS) * blind_hole_volume_mm3(
    BLOCK_TAP_DRILL, BLOCK_TAP_DRILL_DEPTH
)
V_NUT_TAPS = len(NUT_HOLE_POINTS) * blind_hole_volume_mm3(
    NUT_TAP_DRILL, NUT_TAP_DRILL_DEPTH
)
V_NUT_SEAT = math.pi * (SCREW_CLEARANCE_DIA / 2.0) ** 2 * BRACKET_LENGTH + (
    math.pi * ((CBORE_DIA / 2.0) ** 2 - (SCREW_CLEARANCE_DIA / 2.0) ** 2) * CBORE_DEPTH
)


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


def _sketch_mapper(
    adapter: Any, *, u_axis: int, v_axis: int, label: str
) -> Callable[[tuple[float, float, float]], tuple[float, float]]:
    """Map model points (mm) into the ACTIVE sketch, requiring model axis
    ``u_axis`` along the sketch's u and ``v_axis`` along its v (either sign).

    build_ch_rocker_arm_tl_oblique_feed_lever's mapper: the points go through
    ``ModelToSketchTransform`` so only the orientation is assumed, and it is
    checked here.
    """
    import pythoncom
    from win32com.client import VARIANT

    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError(f"{label}: no active sketch")
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def raw(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    base = raw((0.0, 0.0, 0.0))
    for axis, want in ((u_axis, 0), (v_axis, 1)):
        unit = [0.0, 0.0, 0.0]
        unit[axis] = 1.0
        moved = raw(tuple(unit))
        delta = [m - b for m, b in zip(moved, base, strict=True)]
        if abs(abs(delta[want]) - 1.0) > 1e-6:
            raise RuntimeError(
                f"{label}: model axis {axis} maps to sketch {delta!r}, not along "
                f"sketch {'uv'[want]}"
            )

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        u, v, w = raw(model_mm)
        if abs(w) > 1e-4:
            raise RuntimeError(f"{label}: {model_mm} is {w:g} mm off the sketch")
        u, v = round(u, 9), round(v, 9)
        return (0.0 if abs(u) < 1e-9 else u, 0.0 if abs(v) < 1e-9 else v)

    return to_sketch


def _add_reference_point(adapter: Any, uv: tuple[float, float], label: str) -> str:
    """One sketch point straight into the sketch DB (no inference snap:
    _holes.wizard_holes), registered for the adapter's dimension refs."""
    sketch_manager = _early_bound(adapter.currentSketchManager, "ISketchManager")
    previous = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        point = sketch_manager.CreatePoint(uv[0] / 1000.0, uv[1] / 1000.0, 0.0)
    finally:
        sketch_manager.AddToDB = previous
    if point is None:
        raise RuntimeError(f"cannot create the {label} reference point")
    return adapter._register_sketch_entity("Point", point)


def _cbore_diameter_name(adapter: Any) -> str:
    """The nut seat's native counterbore-diameter dimension name.

    build_mg_magnifying_bracket's resolver: the Wizard's own names are
    resolved by role and value, not renamed."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    feature = _early_bound(model.FeatureByName("NutSeat"), "IFeature")
    matches = []
    display = feature.GetFirstDisplayDimension()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        dimension = _early_bound(display.GetDimension(), "IDimension")
        native_name = str(dimension.FullName).split("@")[0].lower()
        if (
            "dia" in native_name
            and abs(float(dimension.SystemValue) * 1000.0 - CBORE_DIA) < 1e-5
        ):
            matches.append(str(dimension.Name))
        display = feature.GetNextDisplayDimension(display)
    if len(matches) != 1:
        raise RuntimeError(
            f"NutSeat: expected one native counterbore diameter, found {matches!r}"
        )
    return matches[0]


async def _nut_pattern_reference(adapter: Any) -> SketchDims:
    """The #4-40 taps' printed offsets from the nut seat's axis.

    The NutTaps wizard dimensions its placement points from the edges, so
    the printed pattern lives here, on the Right plane (X = 0, the nut face
    view's direction; its (u, v) reads model (-Z, Y)). Four points, no lines
    (a construction line printed as a diagonal on TL-22, review c4r3): the
    seat's axis, anchored to the origin by the seat's own stations
    (unprinted), and three taps, each column's Z and each row's Y offset
    from it. A horizontal relation holds the upper-left tap on the
    upper-right's row, a vertical one the lower-right on its column. The
    nut face view shows this sketch to import its dimensions; the part
    saves it hidden.
    """
    label = "nut pattern reference"
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch("Right"))
    to_right = _sketch_mapper(adapter, u_axis=2, v_axis=1, label=label)
    origin = to_right((0.0, 0.0, 0.0))
    if origin != (0.0, 0.0):
        raise RuntimeError(f"{label}: sketch origin maps to {origin}")
    seat_uv = to_right((0.0, -BORE_Y, BORE_Z))
    seat = _add_reference_point(adapter, seat_uv, f"{label} seat axis")
    upper_left, upper_right, lower_right = (
        _add_reference_point(adapter, to_right((0.0, -y, z)), f"{label} {name}")
        for name, y, z in (
            ("upper-left tap", NUT_HOLE_Y[0], NUT_HOLE_Z[0]),
            ("upper-right tap", NUT_HOLE_Y[0], NUT_HOLE_Z[1]),
            ("lower-right tap", NUT_HOLE_Y[1], NUT_HOLE_Z[1]),
        )
    )
    # General point: the horizontal (model Z) dimension, then the vertical.
    await anchor_point_to_origin(adapter, seat, *seat_uv, f"{label} seat axis")
    dims.record("PatternSeatZ", '"BoreZ"')
    dims.record("PatternSeatY", '"BoreY"')
    check(
        f"horizontal_points {label} upper row",
        await adapter.add_sketch_constraint(
            upper_left, upper_right, "horizontal_points"
        ),
    )
    check(
        f"vertical_points {label} right column",
        await adapter.add_sketch_constraint(
            upper_right, lower_right, "vertical_points"
        ),
    )
    for ref, kind, name in (
        (upper_left, "horizontal_distance", "NutPatternZ1"),
        (upper_right, "horizontal_distance", "NutPatternZ2"),
        (upper_right, "vertical_distance", "NutPatternY1"),
        (lower_right, "vertical_distance", "NutPatternY2"),
    ):
        await dimension_between(
            adapter, seat, ref, kind, DRAWING_VALUES[name], f"{label} {name}"
        )
        dims.record(name, '"NutHoleOffset"')
    await ensure_fully_defined(adapter, label)
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    return dims


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for name, value in (
        ("BracketLength", BRACKET_LENGTH),
        ("BracketHeight", BRACKET_HEIGHT),
        ("BracketDepth", BRACKET_DEPTH),
        ("BracketFaceX", BRACKET_FACE_X),
        ("ScrewX1", SCREW_X[0]),
        ("ScrewX2", SCREW_X[1]),
        ("ScrewZ", SCREW_Z),
        ("BoreY", BORE_Y),
        ("BoreZ", BORE_Z),
        ("NutHoleOffset", NUT_HOLE_OFFSET),
    ):
        await set_global(adapter, name, f"{value}mm")

    # --- Bracket: the Y = 0 face on the Top plane, extruded -Y -------------
    profile = SketchDims()
    check("create_sketch bracket", await adapter.create_sketch("Top"))
    to_top = _sketch_mapper(adapter, u_axis=0, v_axis=2, label="bracket profile")
    x1 = FACE_X + BRACKET_LENGTH
    points = [
        to_top((FACE_X, 0.0, 0.0)),
        to_top((x1, 0.0, 0.0)),
        to_top((x1, 0.0, BRACKET_HEIGHT)),
        to_top((FACE_X, 0.0, BRACKET_HEIGHT)),
    ]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="bracket profile",
        dims=profile,
        names=["BracketLength", "BracketHeight", "BracketFaceX"],
        drives=['"BracketLength"', '"BracketHeight"', '"BracketFaceX"'],
    )
    # The #8 stations: X from the -X face, the row from the bottom face, both
    # off the profile's -X/bottom corner (the printed dimensions).
    corner = f"{lines[0]}.start"
    first = _add_reference_point(
        adapter, to_top((FACE_X + SCREW_X[0], 0.0, SCREW_Z)), "#8 station 1"
    )
    second = _add_reference_point(
        adapter, to_top((FACE_X + SCREW_X[1], 0.0, SCREW_Z)), "#8 station 2"
    )
    await dimension_between(
        adapter, corner, first, "horizontal_distance", SCREW_X[0], "#8 station 1"
    )
    profile.record("ScrewX1", '"ScrewX1"')
    await dimension_between(
        adapter, corner, first, "vertical_distance", SCREW_Z, "#8 row"
    )
    profile.record("ScrewZ", '"ScrewZ"')
    check(
        "#8 stations in one row",
        await adapter.add_sketch_constraint(first, second, "horizontal_points"),
    )
    await dimension_between(
        adapter, corner, second, "horizontal_distance", SCREW_X[1], "#8 station 2"
    )
    profile.record("ScrewX2", '"ScrewX2"')
    await ensure_fully_defined(adapter, "bracket profile")
    check("exit_sketch bracket", await adapter.exit_sketch())
    name_last_feature(adapter, "BracketProfile")
    drive_jobs = profile.apply(adapter, "BracketProfile")
    check(
        "extrude bracket",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BRACKET_DEPTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Bracket")
    drive_jobs.append(
        (name_dimensions(adapter, "Bracket", ["BracketDepth"])[0], '"BracketDepth"')
    )
    volume = await volume_check(adapter, "bracket", V_BRACKET, 0.002 * V_BRACKET)

    # --- Block screws: ONE #8-32 tap feature, blind from the Y = 0 face (its
    # +Y normal also proves the extrusion ran -Y). The placement dimensions
    # run from the mid-air origin, so they stay unprinted, driven by the
    # profile's stations.
    block_taps = wizard_holes(
        adapter,
        BLOCK_TAP_SPEC,
        [list(point) for point in BLOCK_SCREW_POINTS],
        (0.0, 1.0, 0.0),
        f"nut bracket block-screw taps ({BLOCK_TAP_SPEC.size})",
        name="BlockTaps",
        expect_dia_mm=BLOCK_TAP_DRILL,
        placement_dims=[
            (
                ("BlockTap1X", '"BracketFaceX" - "ScrewX1"'),
                ("BlockTap1Z", '"ScrewZ"'),
            ),
            (("BlockTap2X", '"ScrewX2" - "BracketFaceX"'), SharedCoordinate(0)),
        ],
    )
    drive_jobs += block_taps.placement_drive_jobs
    volume = await volume_check(
        adapter, "block-screw taps", volume - V_BLOCK_TAPS, 0.01 * V_BLOCK_TAPS
    )

    # --- Nut screws: ONE #4-40 tap feature on the -X face, the nut's square
    # pattern about the seat. On an X face the placement sketch's x runs
    # along model Z and its y along model Y (build_dt_cone_tip_block); the
    # shared coordinates fail loudly if that ever differs.
    nut_taps = wizard_holes(
        adapter,
        NUT_TAP_SPEC,
        [list(point) for point in NUT_HOLE_POINTS],
        (-1.0, 0.0, 0.0),
        f"nut bracket nut-screw taps ({NUT_TAP_SPEC.size})",
        name="NutTaps",
        expect_dia_mm=NUT_TAP_DRILL,
        placement_dims=[
            (
                ("NutHoleZ2", '"BoreZ" + "NutHoleOffset"'),
                ("NutHoleY1", '"BoreY" - "NutHoleOffset"'),
            ),
            (SharedCoordinate(0), ("NutHoleY2", '"BoreY" + "NutHoleOffset"')),
            (("NutHoleZ1", '"BoreZ" - "NutHoleOffset"'), SharedCoordinate(1)),
            (SharedCoordinate(2), SharedCoordinate(0)),
        ],
    )
    drive_jobs += nut_taps.placement_drive_jobs
    volume = await volume_check(
        adapter, "nut-screw taps", volume - V_NUT_TAPS, 0.01 * V_NUT_TAPS
    )

    # --- Nut seat: the spigot's counterbore over the screw's THRU clearance,
    # one native counterbore on the -X face (its sizes from the overrides).
    nut_seat = wizard_holes(
        adapter,
        NUT_SEAT_SPEC,
        [list(NUT_SEAT_POINT)],
        (-1.0, 0.0, 0.0),
        "nut bracket nut seat (spigot counterbore, screw clearance)",
        name="NutSeat",
        expect_dia_mm=SCREW_CLEARANCE_DIA,
        placement_dims=[(("BoreZ", '"BoreZ"'), ("BoreY", '"BoreY"'))],
    )
    drive_jobs += nut_seat.placement_drive_jobs
    if (
        abs(nut_seat.cbore_dia_mm - CBORE_DIA) > 1e-3
        or abs(nut_seat.cbore_depth_mm - CBORE_DEPTH) > 1e-3
    ):
        raise RuntimeError(
            f"nut seat counterbore Ø{nut_seat.cbore_dia_mm:g} x "
            f"{nut_seat.cbore_depth_mm:g}, not Ø{CBORE_DIA:g} x {CBORE_DEPTH:g}"
        )
    volume = await volume_check(
        adapter, "nut seat", volume - V_NUT_SEAT, 0.01 * V_NUT_SEAT
    )
    _require_one_solid_body(adapter, label="nut bracket")
    reference = await _nut_pattern_reference(adapter)
    name_last_feature(adapter, NUT_PATTERN_REFERENCE)
    drive_jobs += reference.apply(adapter, NUT_PATTERN_REFERENCE)

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven nut bracket (equations neutral)", volume, 0.002 * V_BRACKET
    )
    _require_one_solid_body(adapter, label="driven nut bracket")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The one model band: the spigot's counterbore (spec CBORE_BAND); every
    # other size and station prints under the title block.
    set_dimension_bilateral_tolerance(
        adapter,
        "NutSeat",
        _cbore_diameter_name(adapter),
        CBORE_BAND[1],
        CBORE_BAND[0],
        places=CALLOUT_PLACES,
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
