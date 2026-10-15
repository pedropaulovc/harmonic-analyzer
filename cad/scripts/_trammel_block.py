r"""The shared build recipe of the rocker template trammel's two clamp-on
blocks (shop tooling): the pivot block (MHA-CH-006-TL-14,
``build_ch_rocker_arm_tl_trammel_pivot_block``) and the scriber block
(MHA-CH-006-TL-15, ``build_ch_rocker_arm_tl_trammel_scriber_block``). A
builder may not import another builder (test_buildgraph), so the recipe lives
here; each part spec supplies its point holes, slit end and screw stations,
and the shared section comes from ``ch_rocker_arm_tl_trammel_pivot_block_spec``.

Layout (the spec's frame: origin on the point-hole axis, top face, edge A):

* the block is a Top-plane rectangle anchored from the point-hole axis,
  extruded down (-Y) by the stock height;
* the bar slot is a Right-plane rectangle whose floor midpoint carries its
  distance from edge A and its depth, cut through the block's length;
* the slit is a Top-plane rectangle whose inner end's midpoint carries its
  end station and its distance from edge A, cut through the height;
* the point hole(s) are Top-plane circles cut through the height;
* the 10-24 set-screw taps enter edge A (through to the slot); each #8-32
  pinch screw is tapped through both jaws from edge B and its edge-B jaw then
  opened to a close #8 clearance up to the slit (dt_cone_tip_block's pinch).
"""

from __future__ import annotations

import math
from types import ModuleType

import ch_rocker_arm_tl_trammel_spec as kit
from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import name_dimensions
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _holes import DRILL_POINT_H, SharedCoordinate, wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_pmi import author_part_pmi
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    anchor_point_to_point,
    dimension_between,
    ensure_fully_defined,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from ch_rocker_arm_tl_trammel_pivot_block_spec import (
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    BLOCK_WIDTH,
    EDGE_B_JAW,
    PINCH_CLEARANCE_DIA,
    PINCH_CLEARANCE_SPEC,
    PINCH_DEPTH,
    PINCH_TAP_DRILL,
    PINCH_TAP_SPEC,
    POINT_FROM_EDGE_A,
    POINT_HOLE_BAND,
    POINT_HOLE_DIA,
    SET_SCREW_DEPTH,
    SET_SCREW_SPEC,
    SET_SCREW_TAP_DRILL,
    SLIT_WIDTH,
    SLIT_Z,
    SLOT_CUT_RISE,
    SLOT_DEPTH,
    SLOT_FROM_EDGE_A,
    SLOT_WIDTH,
    SLOT_Z0,
    SLOT_Z1,
)

# The parts config prints LOW-CARBON STEEL FLAT; its material_specification
# names the 1018 cold-rolled flat bar the shop stocks.
MATERIAL = "Plain Carbon Steel"
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

# The blind pinch clearance stops at the slit face; its drill point runs on
# through the slit's air. Past the slit's far face its radius must stay
# inside the tap drill, so the point cuts no slot-side-jaw thread.
_CLEARANCE_POINT_H = PINCH_CLEARANCE_DIA / 2.0 * DRILL_POINT_H
if (
    PINCH_CLEARANCE_DIA
    / 2.0
    * max(0.0, _CLEARANCE_POINT_H - SLIT_WIDTH)
    / _CLEARANCE_POINT_H
    >= PINCH_TAP_DRILL / 2.0
):
    raise AssertionError("pinch clearance drill point cuts the slot-side jaw")


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


def _strip_overlap_area(radius: float, half_width: float) -> float:
    """Area a strip of ``half_width`` through a circle's centre shares with it."""
    return 2.0 * (
        half_width * math.sqrt(radius * radius - half_width * half_width)
        + radius * radius * math.asin(half_width / radius)
    )


async def _construction_line(
    adapter, start: tuple[float, float], end: tuple[float, float], label: str
) -> str:
    """A construction line placed without inference: an end on an existing
    vertex merges with it (build_ch_rocker_arm_tl_profile_fixture)."""
    sketch_mgr = adapter.currentSketchManager
    previous_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        line_id = check(
            f"add construction line {label}", await adapter.add_line(*start, *end)
        )
        # ConstructionGeometry is declared on ISketchSegment, not ISketchLine.
        _early_bound(
            adapter._sketch_entities[line_id], "ISketchSegment"
        ).ConstructionGeometry = True
    finally:
        sketch_mgr.AddToDB = previous_add_to_db
    return line_id


async def _edge_anchored_rect(
    adapter,
    points: list[tuple[float, float]],
    *,
    edge: int,
    label: str,
    dims: SketchDims,
    names: tuple[str, str, str, str],
) -> None:
    """An axis-parallel rectangle (``points[0] -> points[1]`` horizontal)
    driven by its length, its width and the midpoint of side ``edge``,
    dimensioned from the sketch origin (``names``: length, width, midpoint
    x, midpoint y). The midpoint is the start of a construction line held at
    the side's midpoint (profile fixture's centred-rectangle recipe)."""
    lines = await add_line_chain(adapter, points)
    for line, direction in zip(lines, ("horizontal", "vertical") * 2, strict=True):
        check(
            f"{label} {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    (x0, y0), (x1, _y), (_x, y2) = points[0], points[1], points[2]
    await dimension_between(
        adapter,
        f"{lines[0]}.start",
        f"{lines[0]}.end",
        "horizontal_distance",
        abs(x1 - x0),
        f"{label} length",
    )
    await dimension_between(
        adapter,
        f"{lines[1]}.start",
        f"{lines[1]}.end",
        "vertical_distance",
        abs(y2 - y0),
        f"{label} width",
    )
    (ax, ay), (bx, by) = points[edge], points[(edge + 1) % 4]
    mid = ((ax + bx) / 2.0, (ay + by) / 2.0)
    if abs(mid[0]) < 1e-9 or abs(mid[1]) < 1e-9:
        raise ValueError(
            f"{label}: an anchor midpoint on an axis has one anchor dimension"
        )
    # The construction line ends on the vertex after the anchored side, off it.
    anchor = await _construction_line(
        adapter, mid, points[(edge + 2) % 4], f"{label} anchor"
    )
    check(
        f"{label} anchor at the side's midpoint",
        await adapter.add_sketch_constraint(f"{anchor}.start", lines[edge], "midpoint"),
    )
    await anchor_point_to_origin(adapter, f"{anchor}.start", *mid, f"{label} anchor")
    for name in names:
        dims.record(name)


async def _point_holes(adapter, hole_x: tuple[float, ...], dims: SketchDims) -> None:
    """The point holes on the Top plane: the first anchored from the origin
    (its axis), the next held to it along X by the scriber spacing."""
    radius = POINT_HOLE_DIA / 2.0
    first = await define_circle(
        adapter,
        hole_x[0],
        -POINT_FROM_EDGE_A,
        radius,
        "point hole 1",
        dims=dims,
        names=(None, "PointFromEdgeA", "PointHoleDia"),
    )
    for index, x in enumerate(hole_x[1:], start=2):
        sketch_mgr = adapter.currentSketchManager
        previous_add_to_db = bool(sketch_mgr.AddToDB)
        sketch_mgr.AddToDB = True
        try:
            circle = await adapter.add_circle(x, -POINT_FROM_EDGE_A, radius)
            check(f"add_circle point hole {index}", circle)
        finally:
            sketch_mgr.AddToDB = previous_add_to_db
        await anchor_point_to_point(
            adapter,
            f"{first}.center",
            f"{circle.data}.center",
            x - hole_x[0],
            0.0,
            f"point hole {index} spacing",
        )
        dims.record("ScriberSpacing")
        check(
            f"dimension point hole {index} diameter",
            await adapter.add_sketch_dimension(
                circle.data, None, "diameter", POINT_HOLE_DIA
            ),
        )
        dims.record(f"PointHoleDia{index}")


def _station_names(prefix: str, count: int) -> list[str]:
    return [prefix] if count == 1 else [f"{prefix}{i}" for i in range(1, count + 1)]


def _placement_dims(x_names: list[str], y_name: str) -> list:
    return [
        ((name, None), (y_name, None) if index == 0 else SharedCoordinate(0))
        for index, name in enumerate(x_names)
    ]


async def build_block(adapter, part: ModuleType, part_name: str) -> dict[str, str]:
    """Build one trammel block from its part spec (pivot or scriber)."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    x0, x1 = part.BLOCK_X0, part.BLOCK_X1
    check("create_part", await adapter.create_part())

    # Block: Top plane (sketch x = model X, sketch y = model -Z), anchored at
    # the end face's edge-A corner from the point-hole axis.
    profile = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Top"))
    points = [(x0, 0.0), (x1, 0.0), (x1, -BLOCK_WIDTH), (x0, -BLOCK_WIDTH)]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="block profile",
        dims=profile,
        names=["BlockLength", "BlockWidth", "HoleFromEnd"],
    )
    await ensure_fully_defined(adapter, "block profile")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    profile.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BLOCK_HEIGHT, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Block")
    name_dimensions(adapter, "Block", ["BlockHeight"])
    v_block = BLOCK_LENGTH * BLOCK_WIDTH * BLOCK_HEIGHT
    volume = await volume_check(adapter, "block", v_block, 0.002 * v_block)

    # Bar slot: Right plane (sketch x = model -Z, sketch y = model Y), from
    # above the top face down to the floor, cut along the whole block.
    slot = SketchDims()
    check("create_sketch slot", await adapter.create_sketch("Right"))
    await _edge_anchored_rect(
        adapter,
        [
            (-SLOT_Z1, -SLOT_DEPTH),
            (-SLOT_Z0, -SLOT_DEPTH),
            (-SLOT_Z0, SLOT_CUT_RISE),
            (-SLOT_Z1, SLOT_CUT_RISE),
        ],
        edge=0,
        label="bar slot",
        dims=slot,
        names=("SlotWidth", "SlotCutHeight", "SlotFromEdgeA", "SlotDepth"),
    )
    await ensure_fully_defined(adapter, "bar slot")
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    slot.apply(adapter, "SlotProfile")
    check(
        "cut slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=2.0 * (max(abs(x0), abs(x1)) + 1.0), both_directions=True
            )
        ),
    )
    name_last_feature(adapter, "Slot")
    v_slot = SLOT_WIDTH * SLOT_DEPTH * BLOCK_LENGTH
    volume = await volume_check(adapter, "bar slot", volume - v_slot, 0.01 * v_slot)
    if abs(SLOT_FROM_EDGE_A - (SLOT_Z0 + SLOT_Z1) / 2.0) > 1e-9:
        raise AssertionError("bar slot sketch is not centred on its printed station")

    # Slit: Top plane, from beyond the near end face to its end station, on
    # the point-hole axis, cut through the height.
    slit = SketchDims()
    check("create_sketch slit", await adapter.create_sketch("Top"))
    z_near, z_far = SLIT_Z - SLIT_WIDTH / 2.0, SLIT_Z + SLIT_WIDTH / 2.0
    start, end = part.SLIT_START_X, part.SLIT_END_X
    await _edge_anchored_rect(
        adapter,
        [(start, -z_far), (end, -z_far), (end, -z_near), (start, -z_near)],
        edge=1,
        label="slit",
        dims=slit,
        names=("SlitCutLength", "SlitWidth", "SlitEnd", "SlitFromEdgeA"),
    )
    await ensure_fully_defined(adapter, "slit")
    check("exit_sketch slit", await adapter.exit_sketch())
    name_last_feature(adapter, "SlitProfile")
    slit.apply(adapter, "SlitProfile")
    check(
        "cut slit",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * (BLOCK_HEIGHT + 1.0), both_directions=True)
        ),
    )
    name_last_feature(adapter, "Slit")
    v_slit = SLIT_WIDTH * BLOCK_HEIGHT * (end - x0)
    volume = await volume_check(adapter, "slit", volume - v_slit, 0.01 * v_slit)

    # Point holes: Top plane circles through the height; the slit has
    # already taken a strip through each.
    holes = SketchDims()
    check("create_sketch point holes", await adapter.create_sketch("Top"))
    await _point_holes(adapter, part.HOLE_X, holes)
    await ensure_fully_defined(adapter, "point holes")
    check("exit_sketch point holes", await adapter.exit_sketch())
    name_last_feature(adapter, "PointHoleProfile")
    holes.apply(adapter, "PointHoleProfile")
    check(
        "cut point holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * (BLOCK_HEIGHT + 1.0), both_directions=True)
        ),
    )
    name_last_feature(adapter, "PointHoles")
    radius = POINT_HOLE_DIA / 2.0
    v_holes = (
        len(part.HOLE_X)
        * BLOCK_HEIGHT
        * (math.pi * radius * radius - _strip_overlap_area(radius, SLIT_WIDTH / 2.0))
    )
    volume = await volume_check(
        adapter, "point holes", volume - v_holes, 0.01 * v_holes
    )

    # Set screws: 10-24 taps from edge A (outward normal -Z) through to the slot.
    set_x_names = _station_names("SetScrewX", len(part.SET_SCREW_X))
    if len(set_x_names) == 1:
        raise AssertionError("trammel blocks carry two set screws")
    set_taps = wizard_holes(
        adapter,
        SET_SCREW_SPEC,
        [[x, -SET_SCREW_DEPTH, 0.0] for x in part.SET_SCREW_X],
        (0.0, 0.0, -1.0),
        f"trammel bar set-screw taps ({SET_SCREW_SPEC.size})",
        name="SetScrewTaps",
        expect_dia_mm=SET_SCREW_TAP_DRILL,
        placement_dims=_placement_dims(set_x_names, "SetScrewDepth"),
    )
    v_set = (
        len(part.SET_SCREW_X) * math.pi * (set_taps.hole_dia_mm / 2.0) ** 2 * SLOT_Z0
    )
    volume = await volume_check(adapter, "set-screw taps", volume - v_set, 0.03 * v_set)

    # Pinch screws: #8-32 tapped through both jaws from edge B (outward
    # normal +Z), then the edge-B jaw opened, blind to the slit face, to the
    # close clearance (dt_cone_tip_block's blind near-jaw clearance).
    pinch_points = [[x, -PINCH_DEPTH, BLOCK_WIDTH] for x in part.PINCH_X]
    pinch_taps = wizard_holes(
        adapter,
        PINCH_TAP_SPEC,
        pinch_points,
        (0.0, 0.0, 1.0),
        f"pinch screw taps ({PINCH_TAP_SPEC.size})",
        name="PinchTaps",
        expect_dia_mm=PINCH_TAP_DRILL,
        placement_dims=_placement_dims(
            _station_names("PinchX", len(part.PINCH_X)), "PinchDepth"
        ),
    )
    v_pinch = (
        len(part.PINCH_X)
        * math.pi
        * (pinch_taps.hole_dia_mm / 2.0) ** 2
        * (BLOCK_WIDTH - SLIT_WIDTH)
    )
    volume = await volume_check(adapter, "pinch taps", volume - v_pinch, 0.03 * v_pinch)
    pinch_clearance = wizard_holes(
        adapter,
        PINCH_CLEARANCE_SPEC,
        pinch_points,
        (0.0, 0.0, 1.0),
        f"pinch screw edge-B jaw clearance ({PINCH_CLEARANCE_SPEC.size} close)",
        name="PinchClearance",
        expect_dia_mm=PINCH_CLEARANCE_DIA,
        placement_dims=_placement_dims(
            _station_names("ClearanceX", len(part.PINCH_X)), "ClearanceDepth"
        ),
    )
    # The point lies in the slit and inside the tap drill: only the annulus
    # over the edge-B jaw is removed.
    v_clearance = (
        len(part.PINCH_X)
        * math.pi
        * (
            (pinch_clearance.hole_dia_mm / 2.0) ** 2
            - (pinch_taps.hole_dia_mm / 2.0) ** 2
        )
        * EDGE_B_JAW
    )
    volume = await volume_check(
        adapter, "pinch clearance", volume - v_clearance, 0.05 * v_clearance
    )
    _require_one_solid_body(adapter, label="trammel block")

    await force_rebuild(adapter)
    await volume_check(adapter, "rebuilt trammel block", volume, 0.002 * v_block)
    _require_one_solid_body(adapter, label="rebuilt trammel block")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "SlotProfile", "SlotWidth", *deviations(kit.SLOT_WIDTH_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "PointHoleProfile", "PointHoleDia", *deviations(POINT_HOLE_BAND)
    )
    if len(part.HOLE_X) > 1:
        set_dimension_bilateral_tolerance(
            adapter,
            "PointHoleProfile",
            "ScriberSpacing",
            *deviations(kit.SCRIBER_SPACING_BAND),
        )
    apply_drawing_precision(adapter, part.DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in part.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The bar's sliding/locating faces carry their Ra on the part (the
    # drawing's symbols are validated against these faces).
    author_part_pmi(adapter, surface_finishes=part.SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        part_name,
        {
            "Manufacturing Notes": part.DRAWING_NOTES,
            "Isometric View Note": part.ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, part_name)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts
