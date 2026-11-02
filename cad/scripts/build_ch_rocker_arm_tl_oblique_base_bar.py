r"""Build the oblique trammel's base bar (MHA-CH-06-TL-20; shop fixture).

A 6061-T6511 flat bar milled to 5.50 wide from the owned 1/2 x 6 bar (owner
ruling #2083), rail-length long, with the HIWIN rail's seven #8-32 tapped
holes on the rail axis (off the bar's centreline, the column-side edge 3.50
from it) and two hold-down slots across it
(``ch_rocker_arm_tl_oblique_base_bar_spec``). One part, one configuration,
two off: the second bar is the same part turned over. Issue #290: an IPS
document; the globals keep their millimetre values with the mm suffix.

Layout: ONE Front-plane profile -- the bar rectangle from its spindle-end
face (model x 0), its -Y side ``RAIL_ROW_Y`` below the rail axis, with the
two slot stadiums inside it, both located from the faced -Y side's corner
(0, -3.50), like every other feature (rule 10) -- extruded +Z by
the faced thickness; the rail holes are one Hole Wizard feature tapped THRU
from the top face. The row's printed lateral station (3.50 from the -Y
edge) lives on a hidden reference sketch, ``RailRowReference``. The leadscrew
brackets' eight #8 holes are one counterbored Hole Wizard feature from the
underside, one printed station per KP08 station; their four rows print from
the -Y edge on a second hidden reference sketch, ``BracketRowReference``.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_base_bar.py
"""

from __future__ import annotations

import math
import sys

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
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _holes import SharedCoordinate, wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_pmi import author_part_pmi
from _part_save import save_part_and_images
from _metric_vendor_dimension import set_metric_vendor_units
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from ch_rocker_arm_tl_oblique_base_bar_spec import (
    BAR_LENGTH,
    BAR_THICK,
    BAR_WIDTH,
    BRACKET_CBORE_DEPTH,
    BRACKET_CBORE_DIA,
    BRACKET_HOLE_DIA,
    BRACKET_HOLE_SPEC,
    BRACKET_WALL_MIN,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FAR_SLOT_RISE,
    FAR_SLOT_X,
    FAR_SLOT_Y,
    HIGH_SIDE_Y,
    ISOMETRIC_VIEW_NOTE,
    LOW_SIDE_Y,
    METRIC_DIMENSIONS,
    NEAR_SLOT_RISE,
    NEAR_SLOT_X,
    NEAR_SLOT_Y,
    RAIL_HOLE_X,
    RAIL_ROW_Y,
    SLOT_RUN,
    SLOT_WIDTH,
    SURFACE_FINISHES,
    TAP_DRILL,
    TAP_SPEC,
    bracket_hole_walls,
)
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_trammel_spec as trammel

PART_NAME = "ch-rocker-arm-tl-oblique-base-bar"
MATERIAL = "6061 Alloy"  # the registry row's example aluminium flat bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

SLOT_AREA = SLOT_RUN * SLOT_WIDTH + math.pi * (SLOT_WIDTH / 2.0) ** 2
V_BAR = (BAR_LENGTH * BAR_WIDTH - 2.0 * SLOT_AREA) * BAR_THICK
V_TAPPED = V_BAR - len(RAIL_HOLE_X) * math.pi * (TAP_DRILL / 2.0) ** 2 * BAR_THICK

# The leadscrew layout's eight bracket holes, station by station (near, far),
# each a row of four (ruling A′), innermost row first: each station shares one
# printed station, each row one printed height.
BRACKET_HOLES = leadscrew.BASE_BAR_HOLES
BRACKET_NEAR_X = BRACKET_HOLES[0][0]
BRACKET_FAR_X = BRACKET_HOLES[-1][0]
BRACKET_ROW_Y = tuple(-lateral for lateral in leadscrew.BAR_SCREW_LATERALS)
if BRACKET_HOLES != tuple(
    (x, y) for x in (BRACKET_NEAR_X, BRACKET_FAR_X) for y in BRACKET_ROW_Y
):
    raise AssertionError("bracket placement assumes two stations on shared rows")
# Each row from the faced -Y edge: 2.425, 1.768, .902, .245.
BRACKET_ROWS = tuple(y - LOW_SIDE_Y for y in BRACKET_ROW_Y)
_walls = bracket_hole_walls(BRACKET_HOLES)
if min(_walls.values()) < BRACKET_WALL_MIN:
    raise AssertionError(f"bracket hole walls under rule 17: {_walls}")
V_BRACKETED = V_TAPPED - len(BRACKET_HOLES) * math.pi * (
    (BRACKET_HOLE_DIA / 2.0) ** 2 * BAR_THICK
    + ((BRACKET_CBORE_DIA / 2.0) ** 2 - (BRACKET_HOLE_DIA / 2.0) ** 2)
    * BRACKET_CBORE_DEPTH
)
# The wizard dimensions each hole from the origin (on the rail axis): the
# first of each station carries the station, the near station's holes the
# rows (the rail row's 3.50 less the row's height); the rest share them.
_ROW_COUNT = len(BRACKET_ROW_Y)
_BRACKET_PLACEMENT = [
    (
        (f"BracketHole{index + 1}X", f'"Bracket{station}X"')
        if row == 0
        else SharedCoordinate(index - row),
        (f"BracketHole{index + 1}Y", f'"RailRowY" - "BracketRow{row + 1}"')
        if index < _ROW_COUNT
        else SharedCoordinate(row),
    )
    for index, (station, row) in enumerate(
        (station, row) for station in ("Near", "Far") for row in range(_ROW_COUNT)
    )
]
# Tight enough that a missing tap (~119 mm^3) or counterbore (~140 mm^3)
# fails; the slots (~2.8e3 mm^3 each) are far above it.
_V_TOL = 40.0


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry (rebind to the
    base ISketchSegment, which declares ``ConstructionGeometry``)."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _stadium(x: float, y_centre: float) -> tuple[tuple[float, float], ...]:
    """One slot across the bar in Front-plane (x, y), counter-clockwise.

    ``y_centre`` is the slot's mid-run centre. Returns
    ``(p1, p2, p3, p4, centre_top, centre_bottom)``: side a runs p1 -> p2 up
    the +X side, the top end arcs about centre_top from p2 to p3, side b runs
    p3 -> p4 down the -X side and the bottom end arcs about centre_bottom from
    p4 back to p1 (build_fr_top_frame's slot_stadium_points, along v).
    """
    r = SLOT_WIDTH / 2.0
    y0 = y_centre - SLOT_RUN / 2.0
    y1 = y0 + SLOT_RUN
    return ((x + r, y0), (x + r, y1), (x - r, y1), (x - r, y0), (x, y1), (x, y0))


async def _slot(
    adapter,
    corner: str,
    x: float,
    y_centre: float,
    located: float,
    prefix: str,
    dims: SketchDims,
) -> None:
    """Draw one closed stadium and locate its lower end centre from ``corner``.

    Each slot's bottom end centre takes its station and rise from the -Y
    side's corner, the one datum the holes use too (c3-r6 review, rule 10:
    the far slot's drop from the +Y side was a second datum in the view; the
    5.50 bar's wall to the +Y side, at ±.08 travel, absorbs the width's
    band).
    Emission order: the width across the sides, the +X side's straight run,
    then the end centre's x and ``located`` height from the corner. The far slot's run is the printed ``SlotRun`` (2X): its
    dimension lands right of the bar, off the part; the near slot's width is
    the printed ``SlotWidth``."""
    p1, p2, p3, p4, c_top, c_bottom = _stadium(x, y_centre)
    label = f"{prefix} slot"
    set_sketch_direct_db(adapter, True)
    side_a = check(f"{label} side a", await adapter.add_line(*p1, *p2))
    end_top = check(f"{label} top end", await adapter.add_arc(*c_top, *p2, *p3))
    side_b = check(f"{label} side b", await adapter.add_line(*p3, *p4))
    end_bottom = check(
        f"{label} bottom end", await adapter.add_arc(*c_bottom, *p4, *p1)
    )
    set_sketch_direct_db(adapter, False)
    for join, a, b in (
        ("side a - top end", f"{side_a}.end", f"{end_top}.start"),
        ("top end - side b", f"{end_top}.end", f"{side_b}.start"),
        ("side b - bottom end", f"{side_b}.end", f"{end_bottom}.start"),
        ("bottom end - side a", f"{end_bottom}.end", f"{side_a}.start"),
    ):
        check(
            f"{label} {join}", await adapter.add_sketch_constraint(a, b, "coincident")
        )
    for side in (side_a, side_b):
        check(
            f"{label} {side} vertical",
            await adapter.add_sketch_constraint(side, None, "vertical"),
        )
    # Tangency closes the shape: both ends' radii follow from the sides'
    # spacing, side b's length from side a's.
    for a, b in (
        (side_a, end_top),
        (end_top, side_b),
        (side_b, end_bottom),
        (end_bottom, side_a),
    ):
        check(
            f"{label} {a} tangent {b}",
            await adapter.add_sketch_constraint(a, b, "tangent"),
        )
    await dimension_between(
        adapter,
        f"{side_b}.end",
        f"{side_a}.start",
        "horizontal_distance",
        SLOT_WIDTH,
        f"{label} width",
    )
    await dimension_between(
        adapter,
        f"{side_a}.start",
        f"{side_a}.end",
        "vertical_distance",
        SLOT_RUN,
        f"{label} run",
    )
    located_end = f"{end_bottom}.center"
    await dimension_between(
        adapter,
        corner,
        located_end,
        "horizontal_distance",
        x,
        f"{label} station",
    )
    await dimension_between(
        adapter,
        corner,
        located_end,
        "vertical_distance",
        located,
        f"{label} rise",
    )
    if prefix == "near":
        dims.record("SlotWidth", '"SlotWidth"')
        dims.record("NearSlotRun", '"SlotRun"')
        dims.record("NearSlotX", '"NearSlotX"')
        dims.record("NearSlotRise", '"NearSlotRise"')
    else:
        dims.record("FarSlotWidth", '"SlotWidth"')
        dims.record("SlotRun", '"SlotRun"')
        dims.record("FarSlotX", '"FarSlotX"')
        dims.record("FarSlotRise", '"FarSlotRise"')


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for name, value in (
        ("BarLength", BAR_LENGTH),
        ("BarWidth", BAR_WIDTH),
        ("BarThick", BAR_THICK),
        ("SlotWidth", SLOT_WIDTH),
        ("SlotRun", SLOT_RUN),
        ("NearSlotX", NEAR_SLOT_X),
        ("FarSlotX", FAR_SLOT_X),
        ("NearSlotRise", NEAR_SLOT_RISE),
        ("FarSlotRise", FAR_SLOT_RISE),
        ("RailRowY", RAIL_ROW_Y),
        ("RailHoleEnd", trammel.RAIL_HOLE_END),
        ("RailHolePitch", trammel.RAIL_HOLE_PITCH),
        ("BracketNearX", BRACKET_NEAR_X),
        ("BracketFarX", BRACKET_FAR_X),
        *(
            (f"BracketRow{row}", value)
            for row, value in enumerate(BRACKET_ROWS, start=1)
        ),
    ):
        await set_global(adapter, name, f"{value}mm")

    # --- Bar profile with both slots, extruded +Z ----------------------------
    profile = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    points = [
        (0.0, LOW_SIDE_Y),
        (BAR_LENGTH, LOW_SIDE_Y),
        (BAR_LENGTH, HIGH_SIDE_Y),
        (0.0, HIGH_SIDE_Y),
    ]
    lines = await add_line_chain(adapter, points)
    # The rail sits off the centreline (the 2026-10-17 widening), so the
    # origin anchor reads the -Y side's own station, the row's, not half the
    # width.
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="bar profile",
        dims=profile,
        names=["BarLength", "BarWidth", "BarLowSide"],
        drives=['"BarLength"', '"BarWidth"', '"RailRowY"'],
    )
    low_corner = f"{lines[0]}.start"  # (0, LOW_SIDE_Y)
    await _slot(
        adapter,
        low_corner,
        NEAR_SLOT_X,
        NEAR_SLOT_Y,
        NEAR_SLOT_RISE,
        "near",
        profile,
    )
    await _slot(
        adapter, low_corner, FAR_SLOT_X, FAR_SLOT_Y, FAR_SLOT_RISE, "far", profile
    )
    await ensure_fully_defined(adapter, "bar profile")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs = profile.apply(adapter, "BarProfile")
    check(
        "extrude bar",
        await adapter.create_extrusion(ExtrusionParameters(depth=BAR_THICK)),
    )
    name_last_feature(adapter, "Bar")
    drive_jobs.append((name_dimensions(adapter, "Bar", ["BarThick"])[0], '"BarThick"'))
    await volume_check(adapter, "slotted bar", V_BAR, _V_TOL)

    # --- Rail holes: one wizard feature tapped THRU from the top face --------
    taps = wizard_holes(
        adapter,
        TAP_SPEC,
        [[x, 0.0, BAR_THICK] for x in RAIL_HOLE_X],
        (0.0, 0.0, 1.0),
        "rail screw taps (#8-32 through)",
        name="RailHoles",
        expect_dia_mm=TAP_DRILL,
        placement_dims=[
            (
                (f"RailHole{k + 1}X", f'"RailHoleEnd" + {k} * "RailHolePitch"'),
                (None, None),
            )
            for k in range(len(RAIL_HOLE_X))
        ],
    )
    drive_jobs += taps.placement_drive_jobs
    await volume_check(adapter, "bar with rail taps", V_TAPPED, _V_TOL)

    # --- The row's lateral station: a reference sketch -----------------------
    # The wizard sets the row on y 0 by an origin relation (a zero coordinate
    # takes no dimension), so the printed 88.90 from the faced -Y edge lives
    # on one line down the end face from the origin to that edge, driven by
    # the station the edge itself reads (the profile's BarLowSide;
    # build_ch_rocker_arm_tl_outline_template's RodSlotReference). It lies on
    # the end face's edge, so it stays a plain sketch line: a construction
    # line's dash font prints over the outline (end bracket, machinist review
    # mr4).
    row_station = SketchDims()
    check("create_sketch rail row reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    row_line = check(
        "rail row station line", await adapter.add_line(0.0, 0.0, 0.0, -RAIL_ROW_Y)
    )
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(adapter, f"{row_line}.start", 0.0, 0.0, "rail row")
    await anchor_point_to_origin(
        adapter, f"{row_line}.end", 0.0, -RAIL_ROW_Y, "rail row station RailRowY"
    )
    row_station.record("RailRowY", '"RailRowY"')
    await ensure_fully_defined(adapter, "rail row reference sketch")
    check("exit_sketch rail row reference", await adapter.exit_sketch())
    name_last_feature(adapter, "RailRowReference")
    drive_jobs += row_station.apply(adapter, "RailRowReference")

    # --- End bracket holes: one counterbored wizard feature from the
    # underside, one station per KP08 station (the row's other holes share it).
    brackets = wizard_holes(
        adapter,
        BRACKET_HOLE_SPEC,
        [[x, y, 0.0] for x, y in BRACKET_HOLES],
        (0.0, 0.0, -1.0),
        "end bracket holes (#8 counterbored from the underside)",
        name="BracketHoles",
        expect_dia_mm=BRACKET_HOLE_DIA,
        placement_dims=_BRACKET_PLACEMENT,
    )
    drive_jobs += brackets.placement_drive_jobs
    await volume_check(adapter, "bar with bracket holes", V_BRACKETED, _V_TOL)

    # --- The bracket rows from the faced -Y edge: a reference sketch ----------
    # The wizard dimensions each row from the origin (on the rail axis), so
    # the printed rows live here: one construction line up from the -Y edge
    # at the far station to the innermost row, and one construction line
    # along each row through both stations; every row dimensions from the
    # line's edge end.
    rows = SketchDims()
    check("create_sketch bracket row reference", await adapter.create_sketch("Front"))
    station, first_row = await add_line_chain(
        adapter,
        [
            (BRACKET_FAR_X, LOW_SIDE_Y),
            (BRACKET_FAR_X, BRACKET_ROW_Y[0]),
            (BRACKET_NEAR_X, BRACKET_ROW_Y[0]),
        ],
        close=False,
    )
    other_rows = []
    for y in BRACKET_ROW_Y[1:]:
        (line,) = await add_line_chain(
            adapter, [(BRACKET_FAR_X, y), (BRACKET_NEAR_X, y)], close=False
        )
        other_rows.append(line)
    for line in (station, first_row, *other_rows):
        _as_construction(adapter, line)
    edge = f"{station}.start"
    await anchor_point_to_origin(
        adapter, edge, BRACKET_FAR_X, LOW_SIDE_Y, "bracket rows' edge point"
    )
    rows.record("BracketRowEdgeX", '"BracketFarX"')
    rows.record("BracketRowEdgeY", '"RailRowY"')
    row_lines = [(f"{station}.end", f"{first_row}.end")] + [
        (f"{line}.start", f"{line}.end") for line in other_rows
    ]
    for index, ((row_start, row_end), value) in enumerate(
        zip(row_lines, BRACKET_ROWS, strict=True), start=1
    ):
        name = str(index)
        check(
            f"vertical_points bracket row {name} -> edge point",
            await adapter.add_sketch_constraint(row_start, edge, "vertical_points"),
        )
        await dimension_between(
            adapter, edge, row_start, "vertical_distance", value, f"BracketRow{name}Y"
        )
        rows.record(f"BracketRow{name}Y", f'"BracketRow{name}"')
        check(
            f"horizontal_points bracket row {name}",
            await adapter.add_sketch_constraint(
                row_end, row_start, "horizontal_points"
            ),
        )
        await dimension_between(
            adapter,
            row_end,
            "origin",
            "horizontal_distance",
            BRACKET_NEAR_X,
            f"bracket row {name} near end",
        )
        rows.record(f"BracketRow{name}NearX", '"BracketNearX"')
    await ensure_fully_defined(adapter, "bracket row reference sketch")
    check("exit_sketch bracket row reference", await adapter.exit_sketch())
    name_last_feature(adapter, "BracketRowReference")
    drive_jobs += rows.apply(adapter, "BracketRowReference")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bar (equations neutral)", V_BRACKETED, _V_TOL)

    # Every model edit -- material, marked set, model-owned places -- precedes
    # the save.
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # The metric vendor lines' stations (the HGR15R rail's holes, the KP08
    # stations; owner ruling 4) print exact millimetres with their own bands,
    # authored on the model's own dimensions.
    for (feature_name, dimension_name), (places, band) in METRIC_DIMENSIONS.items():
        set_dimension_symmetric_tolerance(
            adapter, feature_name, dimension_name, band, display_unit="mm"
        )
        set_metric_vendor_units(adapter, feature_name, dimension_name, places=places)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Both faced seats' Ra 3.2 lives on the MODEL as plain annotations.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    # The reference sketches own printed dimensions but no geometry: hide them
    # so no assembly renders them; the drawing shows them in the plan that
    # imports their dimensions (_drawing_hidden_sketches).
    blank_sketch(adapter, "RailRowReference")
    blank_sketch(adapter, "BracketRowReference")
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
