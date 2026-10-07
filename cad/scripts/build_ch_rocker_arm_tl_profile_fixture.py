r"""Build the rocker arm profile fixture (MHA-CH-006-TL-02; shop fixture).

A milled steel plate carrying twelve bonded strap pads, a bonded hub stand and
four bonded rail rests for the S3/S4 rocker-arm profile setups
(``ch_rocker_arm_tl_profile_fixture_spec``). One is made.

Layout (rocker frame A, the spec's frame): the pads, the stand and the plate
are sketched on the hidden ``PadTop`` plane -- the pad reference -- and built
down from it, so the plate's and the stand's start offsets ARE the printed
drops below the pad tops. The rail rests, which seat on their pocket floors,
are sketched on the hidden ``PlateTop`` plane and built both ways from it, so
their height above it is the printed rest-top height. Every cut is sketched on
``PlateTop`` and cut into the plate. The bonded parts are separate bodies,
built after every cut and hole so no cut ever reaches them.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_profile_fixture.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    _read_member,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    ensure_fully_defined,
    extrude_at_offset,
    feature_name_by_type,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _holes import blind_hole_volume_mm3, wizard_holes
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_profile_fixture_spec import (
    CLAMP_STUD_POINTS,
    CLAMP_STUD_SPEC,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    HOLD_DOWN_CBORE_DEPTH,
    HOLD_DOWN_CBORE_DIA,
    HOLD_DOWN_CLEARANCE_DIA,
    HOLD_DOWN_HOLE_SPEC,
    HOLD_DOWN_POINTS,
    ISOMETRIC_VIEW_NOTE,
    LOCATING_BORE_BAND,
    LOCATING_BORE_DEPTH,
    LOCATING_BORE_DIA,
    LOCATING_BORE_FLOOR_Z,
    PAD_HEIGHT,
    PAD_POCKET_DEPTH,
    PAD_POCKETS,
    PAD_TOP_Z,
    PADS,
    PIVOT_TAP_DRILL_DIA,
    PIVOT_TAP_SPEC,
    PLATE_DROP,
    PLATE_LENGTH,
    PLATE_SOUTH_Y,
    PLATE_THICK,
    PLATE_TOP_Z,
    PLATE_WEST_X,
    PLATE_WIDTH,
    REST_HEIGHT,
    REST_POCKET_DEPTH,
    REST_POCKETS,
    REST_TOP_HEIGHT,
    REST_TOP_Z,
    RESTS,
    ROD_PIN_HOLE_BAND,
    ROD_PIN_HOLE_DEPTH,
    ROD_PIN_HOLE_DIA,
    ROD_PIN_HOLE_XY,
    STAND_BORE,
    STAND_DROP,
    STAND_DROP_BAND,
    STAND_HEIGHT,
    STAND_OD,
    STAND_POCKET_DEPTH,
    STAND_POCKET_DIA,
)

PART_NAME = "ch-rocker-arm-tl-profile-fixture"
MATERIAL = "Plain Carbon Steel"  # the plate; the bonded parts are a few grams
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)
PAD_PLANE = "PadTop"
PLATE_PLANE = "PlateTop"
# plate + 12 pads + hub stand + 4 rail rests
BODY_COUNT = 1 + len(PADS) + 1 + len(RESTS)


def _circle_area(dia: float) -> float:
    return math.pi * dia * dia / 4.0


def _require_bodies(adapter, count: int, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != count:
        raise RuntimeError(f"{label}: expected {count} solid bodies, found {len(bodies)}")


def _rect_points(cx: float, cy: float, length: float, width: float) -> list[tuple[float, float]]:
    x0, x1 = cx - length / 2.0, cx + length / 2.0
    y0, y1 = cy - width / 2.0, cy + width / 2.0
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


async def _rect_sketch(adapter, plane: str, rects, *, label: str, profile: str) -> None:
    """One sketch of axis-parallel rectangles, each anchored at its south-west
    corner (unprinted: the schedules carry the locations)."""
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    for tag, cx, cy, length, width in rects:
        points = _rect_points(cx, cy, length, width)
        lines = await add_line_chain(adapter, points)
        await define_rectilinear_chain(adapter, lines, points, label=f"{label} {tag}")
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, profile)


async def _circle_sketch(adapter, plane: str, x: float, y: float, dia: float, *, profile: str, names) -> None:
    dims = SketchDims()
    check(f"create_sketch {profile}", await adapter.create_sketch(plane))
    await define_circle(adapter, x, y, dia / 2.0, profile, dims=dims, names=names)
    await ensure_fully_defined(adapter, f"{profile} sketch")
    check(f"exit_sketch {profile}", await adapter.exit_sketch())
    name_last_feature(adapter, profile)
    dims.apply(adapter, profile)


def _extrude_both_ways(adapter, up: float, down: float) -> str:
    """Boss-extrude the last exited sketch ``up`` along its plane's normal and
    ``down`` against it (mm), as new bodies: a part seated in a pocket of the
    sketch plane's face, its own dimensions the height above that face and the
    depth into it. Raw ``FeatureExtrusion3`` (``Sd=False``), as
    ``_common.extrude_at_offset`` for the start-offset case."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    sketch_name = feature_name_by_type(adapter, "ProfileFeature")
    if not sketch_name:
        raise RuntimeError("_extrude_both_ways: no sketch found to consume")
    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        sketch_name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"_extrude_both_ways: cannot select sketch {sketch_name!r}")
    feature = model.FeatureManager.FeatureExtrusion3(
        False,  # Sd: both directions
        False,  # Flip side to cut
        False,  # Dir: direction 1 along the plane normal
        0,  # T1: swEndCondBlind
        0,  # T2: swEndCondBlind
        up / 1000.0,  # D1
        down / 1000.0,  # D2
        False,
        False,  # Dchk1/2
        False,
        False,  # Ddir1/2
        0.0,
        0.0,  # Dang1/2
        False,
        False,  # OffsetReverse1/2
        False,
        False,  # TranslateSurface1/2
        False,  # Merge: separate bonded bodies
        False,  # UseFeatScope
        True,  # UseAutoSelect
        0,  # T0: swStartSketchPlane
        0.0,  # StartOffset
        False,  # FlipStartOffset
    )
    model.ClearSelection2(True)
    if feature is None:
        raise RuntimeError("_extrude_both_ways: FeatureExtrusion3 returned None")
    return str(_read_member(feature, "Name"))


def _require_dimension(adapter, full_name: str, mm: float) -> None:
    """The named dimension reads ``mm``: the names follow creation order."""
    dimension = adapter.currentModel.Parameter(full_name)
    if dimension is None:
        raise RuntimeError(f"no dimension {full_name}")
    actual = float(_read_member(dimension, "SystemValue")) * 1000.0
    if abs(actual - mm) > 1e-6:
        raise RuntimeError(f"{full_name} reads {actual:.4f} mm, not {mm:.4f}")


def _require_rest_tops(adapter) -> None:
    """Each rail rest spans its pocket floor to REST_TOP_Z: the two-way
    extrude's direction 1 must be the plate top's outward normal. The body
    box is approximate (IBody2.GetBodyBox), so 0.25 mm; reversed, the rest
    would end 2 mm off at both faces."""
    boxes = [
        tuple(float(value) * 1000.0 for value in _early_bound(body, "IBody2").GetBodyBox())
        for body in _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    ]
    floor = PLATE_TOP_Z - REST_POCKET_DEPTH
    for tag, cx, cy, _length, _width in RESTS:
        over = [box for box in boxes if box[0] < cx < box[3] and box[1] < cy < box[4]]
        found = [
            box for box in over
            if abs(box[5] - REST_TOP_Z) < 0.25 and abs(box[2] - floor) < 0.25
        ]
        if len(found) != 1:
            raise RuntimeError(
                f"rest {tag}: expected one body from Z{floor:g} to Z{REST_TOP_Z:g}; "
                f"bodies over it {over}"
            )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    for plane, offset in ((PAD_PLANE, PAD_TOP_Z), (PLATE_PLANE, PLATE_TOP_Z)):
        check(
            f"create_plane {plane}",
            await adapter.create_plane(
                CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=offset)
            ),
        )
        name_last_feature(adapter, plane)

    # Plate: its outline from the locating bore axis, built down from the pad
    # reference by PlateDrop (the gauge stack) and its own 1 in thickness.
    plate_dims = SketchDims()
    check("create_sketch plate", await adapter.create_sketch(PAD_PLANE))
    outline = _rect_points(
        PLATE_WEST_X + PLATE_LENGTH / 2.0,
        PLATE_SOUTH_Y + PLATE_WIDTH / 2.0,
        PLATE_LENGTH,
        PLATE_WIDTH,
    )
    outline_lines = await add_line_chain(adapter, outline)
    await define_rectilinear_chain(
        adapter,
        outline_lines,
        outline,
        label="plate outline",
        dims=plate_dims,
        names=["PlateLength", "PlateWidth", "PlateWestX", "PlateSouthY"],
    )
    await ensure_fully_defined(adapter, "plate sketch")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    plate_dims.apply(adapter, "PlateProfile")
    extrude_at_offset(adapter, PLATE_THICK, PLATE_DROP, True)
    name_last_feature(adapter, "Plate")
    # Offset bosses expose depth first and start offset second.
    name_dimensions(adapter, "Plate", ["PlateThick", "PlateDrop"])
    volume = PLATE_LENGTH * PLATE_WIDTH * PLATE_THICK
    await volume_check(adapter, "plate", volume, 0.001 * volume)

    # Pockets for the bonded parts.
    for rects, depth, label, profile, feature in (
        (PAD_POCKETS, PAD_POCKET_DEPTH, "pad pockets", "PadPocketProfile", "PadPockets"),
        (REST_POCKETS, REST_POCKET_DEPTH, "rest pockets", "RestPocketProfile", "RestPockets"),
    ):
        await _rect_sketch(adapter, PLATE_PLANE, rects, label=label, profile=profile)
        check(
            f"cut {label}",
            await adapter.create_cut_extrude(ExtrusionParameters(depth=depth)),
        )
        name_last_feature(adapter, feature)
        removed = sum(length * width * depth for _t, _x, _y, length, width in rects)
        volume = await volume_check(adapter, label, volume - removed, 0.01 * removed)

    # Hub stand counterbore, then the reamed locating bore below it.
    for profile, feature, dia, depth, dia_name, depth_name, removed_depth in (
        (
            "StandPocketProfile",
            "StandPocket",
            STAND_POCKET_DIA,
            STAND_POCKET_DEPTH,
            "StandPocketDia",
            "StandPocketDepth",
            STAND_POCKET_DEPTH,
        ),
        (
            "LocatingBoreProfile",
            "LocatingBore",
            LOCATING_BORE_DIA,
            LOCATING_BORE_DEPTH,
            "LocatingBoreDia",
            "LocatingBoreDepth",
            LOCATING_BORE_DEPTH - STAND_POCKET_DEPTH,
        ),
    ):
        await _circle_sketch(
            adapter,
            PLATE_PLANE,
            0.0,
            0.0,
            dia,
            profile=profile,
            names=(None, None, dia_name),
        )
        check(f"cut {feature}", await adapter.create_cut_extrude(ExtrusionParameters(depth=depth)))
        name_last_feature(adapter, feature)
        name_dimensions(adapter, feature, [depth_name])
        removed = _circle_area(dia) * removed_depth
        volume = await volume_check(adapter, feature, volume - removed, 0.01 * removed)

    await _circle_sketch(
        adapter,
        PLATE_PLANE,
        *ROD_PIN_HOLE_XY,
        ROD_PIN_HOLE_DIA,
        profile="RodPinHoleProfile",
        names=("RodPinHoleX", "RodPinHoleY", "RodPinHoleDia"),
    )
    check(
        "cut rod pin hole",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=ROD_PIN_HOLE_DEPTH)),
    )
    name_last_feature(adapter, "RodPinHole")
    name_dimensions(adapter, "RodPinHole", ["RodPinHoleDepth"])
    removed = _circle_area(ROD_PIN_HOLE_DIA) * ROD_PIN_HOLE_DEPTH
    volume = await volume_check(adapter, "rod pin hole", volume - removed, 0.01 * removed)

    # Native Hole Wizard holes, all cut before any bonded body exists.
    hold_down = wizard_holes(
        adapter,
        HOLD_DOWN_HOLE_SPEC,
        [[x, y, PLATE_TOP_Z] for x, y in HOLD_DOWN_POINTS],
        (0.0, 0.0, 1.0),
        "hold-down counterbores (1/2 socket head)",
        name="HoldDownHoles",
        expect_dia_mm=HOLD_DOWN_CLEARANCE_DIA,
    )
    removed = len(HOLD_DOWN_POINTS) * (
        _circle_area(hold_down.cbore_dia_mm or HOLD_DOWN_CBORE_DIA) * HOLD_DOWN_CBORE_DEPTH
        + _circle_area(hold_down.hole_dia_mm) * (PLATE_THICK - HOLD_DOWN_CBORE_DEPTH)
    )
    volume = await volume_check(adapter, "hold-down holes", volume - removed, 0.01 * removed)

    studs = wizard_holes(
        adapter,
        CLAMP_STUD_SPEC,
        [[x, y, PLATE_TOP_Z] for x, y in CLAMP_STUD_POINTS],
        (0.0, 0.0, 1.0),
        "strap-clamp stud taps (3/8-16)",
        name="ClampStudTaps",
    )
    removed = len(CLAMP_STUD_POINTS) * blind_hole_volume_mm3(
        studs.hole_dia_mm, CLAMP_STUD_SPEC.depth_mm
    )
    volume = await volume_check(adapter, "clamp stud taps", volume - removed, 0.03 * removed)

    pivot_tap = wizard_holes(
        adapter,
        PIVOT_TAP_SPEC,
        [[0.0, 0.0, LOCATING_BORE_FLOOR_Z]],
        (0.0, 0.0, 1.0),
        "pivot screw tap (#10-24)",
        name="PivotScrewTap",
        expect_dia_mm=PIVOT_TAP_DRILL_DIA,
    )
    removed = blind_hole_volume_mm3(pivot_tap.hole_dia_mm, PIVOT_TAP_SPEC.depth_mm)
    volume = await volume_check(adapter, "pivot screw tap", volume - removed, 0.03 * removed)
    plate_volume = volume
    _require_bodies(adapter, 1, label="machined plate")

    # Bonded parts: separate bodies, each top on its reference.
    check("create_sketch pads", await adapter.create_sketch(PAD_PLANE))
    for tag, cx, cy, length, width in PADS:
        points = _rect_points(cx, cy, length, width)
        lines = await add_line_chain(adapter, points)
        await define_rectilinear_chain(adapter, lines, points, label=f"pad {tag}")
    await ensure_fully_defined(adapter, "pads sketch")
    check("exit_sketch pads", await adapter.exit_sketch())
    name_last_feature(adapter, "PadProfile")
    check(
        "extrude pads",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PAD_HEIGHT, reverse_direction=True, merge_result=False)
        ),
    )
    name_last_feature(adapter, "Pads")
    name_dimensions(adapter, "Pads", ["PadHeight"])
    added = sum(length * width * PAD_HEIGHT for _t, _x, _y, length, width in PADS)
    volume = await volume_check(adapter, "pads", volume + added, 0.005 * added)

    stand_dims = SketchDims()
    check("create_sketch stand", await adapter.create_sketch(PAD_PLANE))
    await define_circle(
        adapter, 0.0, 0.0, STAND_OD / 2.0, "stand OD", dims=stand_dims, names=(None, None, "StandOD")
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        STAND_BORE / 2.0,
        "stand bore",
        dims=stand_dims,
        names=(None, None, "StandBore"),
    )
    await ensure_fully_defined(adapter, "stand sketch")
    check("exit_sketch stand", await adapter.exit_sketch())
    name_last_feature(adapter, "StandProfile")
    stand_dims.apply(adapter, "StandProfile")
    extrude_at_offset(adapter, STAND_HEIGHT, STAND_DROP, True, merge_result=False)
    name_last_feature(adapter, "Stand")
    name_dimensions(adapter, "Stand", ["StandHeight", "StandDrop"])
    added = (_circle_area(STAND_OD) - _circle_area(STAND_BORE)) * STAND_HEIGHT
    volume = await volume_check(adapter, "hub stand", volume + added, 0.005 * added)

    # Rail rests seat on their pocket floors: sketched on the plate top, each
    # stands RestTopHeight above it and runs its pocket depth down to the floor.
    check("create_sketch rests", await adapter.create_sketch(PLATE_PLANE))
    for tag, cx, cy, length, width in RESTS:
        points = _rect_points(cx, cy, length, width)
        lines = await add_line_chain(adapter, points)
        await define_rectilinear_chain(adapter, lines, points, label=f"rest {tag}")
    await ensure_fully_defined(adapter, "rests sketch")
    check("exit_sketch rests", await adapter.exit_sketch())
    name_last_feature(adapter, "RestProfile")
    _extrude_both_ways(adapter, REST_TOP_HEIGHT, REST_POCKET_DEPTH)
    name_last_feature(adapter, "Rests")
    name_dimensions(adapter, "Rests", ["RestTopHeight", "RestSeatDepth"])
    _require_dimension(adapter, "RestTopHeight@Rests", REST_TOP_HEIGHT)
    _require_dimension(adapter, "RestSeatDepth@Rests", REST_POCKET_DEPTH)
    added = sum(length * width * REST_HEIGHT for _t, _x, _y, length, width in RESTS)
    volume = await volume_check(adapter, "rail rests", volume + added, 0.005 * added)
    _require_bodies(adapter, BODY_COUNT, label="built-up fixture")
    _require_rest_tops(adapter)

    blank_reference_geometry(adapter, ((PAD_PLANE, "PLANE"), (PLATE_PLANE, "PLANE")))
    await force_rebuild(adapter)
    await volume_check(adapter, "rebuilt fixture", volume, 0.001 * plate_volume)
    _require_bodies(adapter, BODY_COUNT, label="rebuilt fixture")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "LocatingBoreProfile", "LocatingBoreDia", *deviations(LOCATING_BORE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "RodPinHoleProfile", "RodPinHoleDia", *deviations(ROD_PIN_HOLE_BAND)
    )
    if STAND_DROP_BAND[0] != -STAND_DROP_BAND[1]:
        raise AssertionError("the hub stand drop band is symmetric by ruling B")
    set_dimension_symmetric_tolerance(adapter, "Stand", "StandDrop", STAND_DROP_BAND[0])
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
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
