r"""Create the curated machinist drawing for the green-painted top-frame casting.

The SLDPRT remains authoritative.  This recipe supplies only the ring's views,
profile dimensions, hole table, hole callouts and manufacturing notes; every
shared sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
casting carries no datums or frames.  Every hole size and station is native
-- a plan hole table off the rear-left outer corner (column bores, gooseneck
bore, hanger-stud holes, keeper taps) and a Hole Wizard callout on the
front-elevation side-screw taps -- the profile, window, boss, gusset and
spot-face sizes are marked model dimensions, the rail widths, crossbar, boss
stack heights and top flange are drawing dimensions on view edges, the web
thickness rides a rail T-section (SECTION A-A, cut across the plan), and the
notes say which faces are machined.

The finished envelope is 446.2 x 276.2 x 47.3 over the corner bosses, with a
428.2 x 262.0 rectangular rail outside profile around the 359.8 x 186.0 clear
window, a 36.5-tall webbed ring band, four Ø52.2 corner bosses bored Ø25.5 to
clamp the columns, a Ø17 gooseneck bore through the east-rail hub, and an
integral crossbar carrying two Ø13.49 hanger-stud holes.  The sheet runs
1:2; the front elevation and the section drop to 1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_top_frame.py top-frame
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_native_hole_callout,
    add_property_linked_note,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    insert_hole_table,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import blind_cut_dia_mm
from build_top_frame import (
    BAR_X0,
    BAR_X1,
    BORE_DIA,
    BOSS_ABOVE,
    BOSS_BELOW,
    BOSS_DIA,
    COLUMN_X,
    FLANGE,
    FLANGE_BOT_Y,
    FRONT_COLUMN_Z,
    GOOSENECK_BORE_DIA,
    GOOSENECK_X,
    GOOSENECK_Z,
    HALF_H,
    HUB_BOSS_DROP,
    HUB_GUSSET_HALF_OUT,
    INNER_X,
    INNER_Z,
    KEEPER_TAP_SPEC,
    KEEPER_TAP_X,
    KEEPER_TAP_Z_FRONT,
    KEEPER_TAP_Z_REAR,
    OUTER_X,
    OUTER_Z,
    REAR_COLUMN_Z,
    RING_HEIGHT,
    SIDE_TAP_SPEC,
    STUD_HOLE_DIA,
    STUD_Z_FRONT,
    STUD_Z_REAR,
    WEB_T,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    remove_notes_matching,
    view_name,
)
from top_frame_spec import SET_SCREW_TAP_NOTE


SPEC = DRAWINGS_BY_NAME["top_frame"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 2.0)  # 1:2 whole sheet (446.2 mm envelope over the bosses)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 0.5
FRONT_SCALE = 0.25  # the 1:4 front elevation and section

# Plan extents including the proud corner bosses (the straight rails alone
# stop at x +/-214.1 / z +/-131.0): x +/-223.1 -> 446.2 and z +/-138.1 ->
# 276.2 envelope; the boss stack is 47.3 tall around the 36.5 rail band.
PLAN_HALF_X = COLUMN_X + BOSS_DIA / 2.0  # 223.1
PLAN_HALF_Z = abs(FRONT_COLUMN_Z) + BOSS_DIA / 2.0  # 138.1
BOSS_BAND = RING_HEIGHT + BOSS_ABOVE + BOSS_BELOW  # 47.3
STUD_X = (BAR_X0 + BAR_X1) / 2.0  # -15.0 crossbar centreline
BOSS_TOP_Y = HALF_H + BOSS_ABOVE  # +22.75 (boss top, the elevation's top)
BOSS_BOTTOM_Y = -(HALF_H + BOSS_BELOW)  # -24.55
HUB_BOTTOM_Y = -(HALF_H + HUB_BOSS_DROP)  # -26.25 (hub boss, the lowest point)
# The elevation is placed on its bounding box, which the hub boss makes
# asymmetric in Y: model y 0 sits this far ABOVE the view centre (mm).
FRONT_BBOX_MID_Y = (BOSS_TOP_Y + HUB_BOTTOM_Y) / 2.0  # -1.75
WEB_IN_X = COLUMN_X - WEB_T / 2.0  # 190.65
WEB_OUT_X = COLUMN_X + WEB_T / 2.0  # 203.35

# Sheet layout (meters). The plan defines the profile and carries the hole
# table; the front elevation makes the 36.5 rail band, the 47.3 boss stack,
# the top flange, the spot-faced side-screw seats and their taps visible;
# SECTION A-A (cut across the plan at z +36, clear of every hole, the hub
# and its gussets) shows the rails' T-section for the web thickness.
TOP_CENTER = (0.135, 0.175)
FRONT_CENTER = (0.345, 0.130)
SECTION_CUT_Z = 36.0
SECTION_CENTER = (0.345, 0.099)
# The cut line runs the plan's width on the sheet: from just inside the left
# zone margin (the plan's outline at this height is the east rail at x 0.028)
# to just past the west rail.  Raising it above the set-screw note keeps the
# cutting plane readable; the Depth dimension remains on the right flank.
SECTION_LINE = ((0.019, 0.157), (0.2485, 0.157))

if not (
    HUB_GUSSET_HALF_OUT + GOOSENECK_Z + 1.0
    < SECTION_CUT_Z
    < min(KEEPER_TAP_Z_REAR, STUD_Z_REAR) - STUD_HOLE_DIA / 2.0 - 1.0
):
    raise AssertionError("section A-A must cut clear of the hub gussets and holes")


def _plan_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point for a plan station (machine X, Z in mm), top view."""
    return (
        TOP_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        TOP_CENTER[1] - z_mm * VIEW_SCALE / 1000.0,
    )


def _front_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point for a model (X, Y) in the 1:4 front elevation."""
    return (
        FRONT_CENTER[0] + x_mm * FRONT_SCALE / 1000.0,
        FRONT_CENTER[1] + (y_mm - FRONT_BBOX_MID_Y) * FRONT_SCALE / 1000.0,
    )


if abs(SECTION_LINE[0][1] - _plan_xy(0.0, SECTION_CUT_Z)[1]) > 1e-9:
    raise AssertionError("section cut line does not sit at SECTION_CUT_Z on the plan")


# Per-view survivors of the marked-dimension import. Width/Depth are the straight
# rail outside profile, not the boss envelope; WinWidth/WinDepth the clear
# window; C0Dia the NW corner boss's circle (leadered above the plan, left of
# the Width dimension's text); GussetRunE/RiseE the legs of the front-west
# junction gusset (west window); S0Dia the spot-face, leadered above the
# elevation.
TOP_KEEP = {
    "Width": (
        TOP_CENTER[0],
        TOP_CENTER[1] + PLAN_HALF_Z * VIEW_SCALE / 1000.0 + 0.012,
    ),
    # Depth rides the RIGHT flank (the section cut line runs off the left
    # one), below the hole table's foot and above the elevation's dimensions.
    "Depth": (0.2566, 0.120),
    # Window width along the rear rail's solid band (inside the rail outline,
    # between its inner face and the hidden web line) so it never crosses the
    # window depth, which stands inside the west half-window.
    "WinWidth": (0.170, 0.1255),
    "WinDepth": (0.205, 0.175),
    "C0Dia": (0.075, 0.2495),
    "GussetRunE": (0.160, 0.205),
    "GussetRiseE": (0.150, 0.217),
}
FRONT_KEEP = {
    # On the elevation's centreline: the spot-face sketch sits on a NEGATIVE
    # Front-plane offset, which mirrors sketch x (build_top_frame docstring),
    # so S0 may resolve to either boss -- the leader is the same length from
    # here whichever it is.
    "S0Dia": (FRONT_CENTER[0], 0.152),
}
# Below-text on the marked dimensions: the instance count the sketch cannot
# say, and the spot-face's depth in words (a full flat on the barrel).
DIMENSION_CALLOUTS = {
    "C0Dia": "4X BOSS",
    "S0Dia": "SPOT-FACE FLAT, 4X (2 PER SIDE)",
    "GussetRunE": "4X GUSSETS",
}

# Hole table: top-left anchor, right of the plan and above the elevation; the
# plan-scale note moves above it.  The table origin is the VIRTUAL rear-left
# outer corner (the boss barrels round every real corner), selected as the
# two outer rail edges.
HOLE_TABLE_ANCHOR = (0.256, 0.250)
TOP_VIEW_NOTE_XY = (0.262, 0.259)
# The elevation's smaller scale note occupies the narrow lane between the
# plan-depth dimension and side-tap callout.
FRONT_VIEW_NOTE_XY = (0.264, 0.116)
# Set-screw flag note, inside the east half-window, arrow on the gooseneck bore.
SET_SCREW_NOTE_XY = (0.056, 0.152)
# Side-tap Hole Wizard callout, between the elevation and the section.
SIDE_TAP_CALLOUT_XY = (0.326, 0.114)
# Plan drawing dimensions: front rail width above the front rail (clear of
# the Width dimension), crossbar width beside the crossbar in the west window.
FR_RAIL_TEXT_XY = (_plan_xy(100.0, 0.0)[0], 0.2475)
BAR_TEXT_XY = (0.150, _plan_xy(0.0, 30.0)[1])
# Elevation heights: boss stack + boss-proud outside on the left (smallest
# span nearest), the rail band and top flange inside the elevation between
# the bosses.
STACK_TEXT_XY = (0.264, _front_xy(0.0, 0.0)[1])
BOSS_ABOVE_TEXT_XY = (0.278, _front_xy(0.0, HALF_H + BOSS_ABOVE / 2.0)[1])
RING_TEXT_XY = (_front_xy(92.0, 0.0)[0], _front_xy(0.0, 0.0)[1])
FLANGE_TEXT_XY = (_front_xy(140.0, 0.0)[0], _front_xy(0.0, HALF_H - FLANGE / 2.0)[1])
# Section dimension text sits below the +X T; only the text placement is a
# sheet literal.  Edge picks come from the section view's model transform.
WEB_TEXT_XY = (0.39425, 0.0895)
SIDE_RAIL_TEXT_XY = (0.39425, 0.0835)

# Plan hole pattern, in hole-table order: 4X column bores, the gooseneck
# bore, 2X hanger-stud holes, 2X keeper taps (the tap drill is the modeled
# hole).  Each row is (x, z, modeled diameter) in machine mm.
KEEPER_TAP_DIA = blind_cut_dia_mm(KEEPER_TAP_SPEC)
SIDE_TAP_DIA = blind_cut_dia_mm(SIDE_TAP_SPEC)
ALL_HOLES = (
    *(
        (sx * COLUMN_X, z, BORE_DIA)
        for sx in (-1.0, 1.0)
        for z in (FRONT_COLUMN_Z, REAR_COLUMN_Z)
    ),
    (GOOSENECK_X, GOOSENECK_Z, GOOSENECK_BORE_DIA),
    (STUD_X, STUD_Z_FRONT, STUD_HOLE_DIA),
    (STUD_X, STUD_Z_REAR, STUD_HOLE_DIA),
    (KEEPER_TAP_X, KEEPER_TAP_Z_FRONT, KEEPER_TAP_DIA),
    (KEEPER_TAP_X, KEEPER_TAP_Z_REAR, KEEPER_TAP_DIA),
)


def _view_edges(
    adapter: Any, view: Any
) -> tuple[list[tuple[float, float, float, float, Any]], list[tuple[tuple[float, ...], Any]]]:
    """Every model edge shown in ``view`` (hidden lines included).

    Returns ``(circles, lines)``: circles as ``(cx, cy, cz, radius, edge)`` and
    lines as ``(LineParams, edge)``, all in model metres.  Selecting entities
    topologically keeps every pick off the sheet-coordinate tolerance -- the
    chamfered bore rims, the boss/rail junctions and the hub's hidden outlines
    all sit within a millimetre of each other on the sheet.
    """
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    circles: list[tuple[float, float, float, float, Any]] = []
    lines: list[tuple[tuple[float, ...], Any]] = []
    for component in components:
        visible_edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(
                    c, 1
                ),  # swViewEntityType_Edge
                default=(),
            )
            or ()
        )
        for edge in visible_edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve.IsCircle():
                parameters = tuple(float(value) for value in curve.CircleParams)
                circles.append(
                    (parameters[0], parameters[1], parameters[2], parameters[6], edge)
                )
                continue
            if curve.IsLine():
                parameters = tuple(float(value) for value in curve.LineParams)
                lines.append((parameters, edge))
    return circles, lines


def _circle_edge(
    circles: list[tuple[float, float, float, float, Any]],
    *,
    radius_mm: float,
    label: str,
    x_mm: float | None = None,
    y_mm: float | None = None,
    z_mm: float | None = None,
    prefer: str = "top",
) -> Any:
    """One circular edge of ``radius_mm`` whose centre matches the given axes.

    Coincident rims (a bore's two ends, a boss's two rims) are legitimate: the
    ``prefer`` rule picks the top-most (``"top"``, the plan's visible rim) or
    the front-most (``"front"``, lowest z, the elevation's visible rim).
    """
    matches = [
        (cx, cy, cz, edge)
        for cx, cy, cz, radius, edge in circles
        if abs(radius - radius_mm / 1000.0) <= 5e-5
        and (x_mm is None or abs(cx - x_mm / 1000.0) <= 5e-5)
        and (y_mm is None or abs(cy - y_mm / 1000.0) <= 5e-5)
        and (z_mm is None or abs(cz - z_mm / 1000.0) <= 5e-5)
    ]
    if not matches:
        raise RuntimeError(
            f"top-frame view has no circular edge for {label} "
            f"(x={x_mm!r}, y={y_mm!r}, z={z_mm!r}, diameter {2 * radius_mm:g} mm)"
        )
    if prefer == "top":
        matches.sort(key=lambda item: -item[1])
    elif prefer == "front":
        matches.sort(key=lambda item: item[2])
    else:
        raise ValueError(f"unknown circle preference {prefer!r}")
    return matches[0][3]


def _line_edge(
    lines: list[tuple[tuple[float, ...], Any]],
    *,
    label: str,
    along: str,
    x_mm: float | None = None,
    y_mm: float | None = None,
    z_mm: float | None = None,
) -> Any:
    """One straight edge running ``along`` an axis through the given station.

    ``LineParams`` is ``(point xyz, direction xyz)``; an edge is a match when
    its direction is the requested axis and its point lies on every axis
    station given.  Coincident candidates (front/rear rail, both ends of a
    face) project to the same sheet line; the top-most is taken so a plan
    pick lands on the visible rim, never on a hidden one below it.
    """
    axis = {"x": 3, "y": 4, "z": 5}[along]
    matches = [
        (parameters[1], edge)
        for parameters, edge in lines
        if abs(parameters[axis]) >= 0.99
        and (x_mm is None or abs(parameters[0] - x_mm / 1000.0) <= 2e-6)
        and (y_mm is None or abs(parameters[1] - y_mm / 1000.0) <= 2e-6)
        and (z_mm is None or abs(parameters[2] - z_mm / 1000.0) <= 2e-6)
    ]
    if not matches:
        raise RuntimeError(
            f"top-frame view has no straight edge for {label} "
            f"(along {along}, x={x_mm!r}, y={y_mm!r}, z={z_mm!r})"
        )
    matches.sort(key=lambda item: -item[0])
    return matches[0][1]


def _dimension_entities(
    adapter: Any,
    view: Any,
    entities: tuple[Any, ...],
    *,
    text_xy: tuple[float, float],
    orientation: str,
    label: str,
) -> Any:
    """Dimension across topologically selected drawing-view entities.

    ``IView::SelectEntity`` puts each model entity into the drawing selection
    (the same call ``_drawing_common._select_view_entity`` makes for callouts
    and attached notes), then the matching ``IModelDoc2.Add*Dimension2``
    creates the dimension with its text at ``text_xy`` (sheet metres).
    """
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r} ({label})")
    draw.ClearSelection2(True)
    for index, entity in enumerate(entities):
        if not view.SelectEntity(entity, index > 0):
            raise RuntimeError(f"failed to select {label} entity {index}")
    if orientation == "horizontal":
        dimension = draw.AddHorizontalDimension2(text_xy[0], text_xy[1], 0.0)
    elif orientation == "vertical":
        dimension = draw.AddVerticalDimension2(text_xy[0], text_xy[1], 0.0)
    elif orientation == "smart":
        dimension = draw.AddDimension2(text_xy[0], text_xy[1], 0.0)
    else:
        raise ValueError(f"unknown dimension orientation {orientation!r}")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if dimension is None:
        raise RuntimeError(f"failed to add the {label} {orientation} dimension")
    return dimension


def _plan_hole_table_entities(
    circles: list[tuple[float, float, float, float, Any]],
    lines: list[tuple[tuple[float, ...], Any]],
) -> tuple[tuple[Any, ...], Any, Any, Any]:
    """Hole rims, the rear/left outer rail edges and the gooseneck rim, plan view.

    Every plan corner is rounded by a boss barrel, so no corner vertex exists
    to anchor the hole table; the caller passes the two outer rail edges as
    ``datum_axes`` and the table origin lands on their VIRTUAL intersection
    -- the theoretical sharp rear-left corner every LOC value is measured
    from.  Both bore ends and the chamfer edge project concentrically; the
    top rim (the visible one) is taken for each hole.
    """
    hole_edges = tuple(
        _circle_edge(
            circles,
            radius_mm=diameter / 2.0,
            x_mm=x,
            z_mm=z,
            label=f"hole ({x:g}, {z:g})",
            prefer="top",
        )
        for x, z, diameter in ALL_HOLES
    )
    rear_edge = _line_edge(lines, label="rear outer rail edge", along="x", z_mm=OUTER_Z)
    left_edge = _line_edge(lines, label="left outer rail edge", along="z", x_mm=-OUTER_X)
    gooseneck_edge = hole_edges[4]
    return hole_edges, rear_edge, left_edge, gooseneck_edge


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open top-frame source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Top View Note",
            "Front View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Top View Note",
            "Front View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Top Frame Ring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "top frame; webbed gray iron ring casting; column bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 4))
    # Hidden lines ON in every orthographic view: the elevation shows the
    # column bores through the bosses and the webbed panels' recesses.
    for view in (top, front):
        set_hidden_lines_visible(adapter, view)

    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(
        adapter, [*top_annotations, *front_annotations], DIMENSION_CALLOUTS
    )
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError(
            "failed to add ASME center marks to the ring bores and stud holes"
        )

    plan_circles, plan_lines = _view_edges(adapter, top)
    hole_entities, rear_edge, left_edge, gooseneck_edge = _plan_hole_table_entities(
        plan_circles, plan_lines
    )
    # One complete plan hole table: column bores, gooseneck bore, hanger-stud
    # holes and keeper taps, every station under the title-block tolerance
    # (ordinary X LOC / Y LOC headers, no position frame to feed); the SIZE
    # column is the native callout (the keeper rows carry the thread + depth).
    insert_hole_table(
        adapter,
        top,
        datum_xy=_plan_xy(-OUTER_X, OUTER_Z),
        hole_points=tuple(_plan_xy(x + diameter / 2.0, z) for x, z, diameter in ALL_HOLES),
        datum_axes=(rear_edge, left_edge),
        hole_entities=hole_entities,
        # X from the left outer rail face (x = -214.1), Y from the rear outer
        # rail face (z = +131), increasing toward the front.
        expected_locations_mm=tuple(
            (x + OUTER_X, OUTER_Z - z) for x, z, _diameter in ALL_HOLES
        ),
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="top-frame plan",
    )
    # The set-screw tap has no circle in either view (it enters the hub's
    # east face): flag it from the bore it breaks into.
    add_attached_note(
        adapter,
        top,
        text=SET_SCREW_TAP_NOTE,
        entity=gooseneck_edge,
        note_xy=SET_SCREW_NOTE_XY,
        label="gooseneck set-screw tap",
    )
    # Plan drawing dimensions: the front/rear rail width across the front
    # rail's outer and window faces (top-rim chamfer lower edges), the
    # crossbar width across its two flanks.
    _dimension_entities(
        adapter,
        top,
        (
            _line_edge(plan_lines, label="front rail window face", along="x", z_mm=-INNER_Z),
            _line_edge(plan_lines, label="front rail outer face", along="x", z_mm=-OUTER_Z),
        ),
        text_xy=FR_RAIL_TEXT_XY,
        orientation="vertical",
        label="front/rear rail width",
    )
    _dimension_entities(
        adapter,
        top,
        (
            _line_edge(plan_lines, label="crossbar east flank", along="z", x_mm=BAR_X0),
            _line_edge(plan_lines, label="crossbar west flank", along="z", x_mm=BAR_X1),
        ),
        text_xy=BAR_TEXT_XY,
        orientation="horizontal",
        label="crossbar width",
    )

    # Front elevation: the boss stack, the boss-proud step, the rail band and
    # the top flange as drawing dimensions on topologically picked edges (the
    # elevation's bounding box is asymmetric, so no sheet-coordinate picks),
    # plus the side-screw tap's native callout on the front-left seat.
    front_circles, front_lines = _view_edges(adapter, front)
    boss_top = _circle_edge(
        front_circles,
        radius_mm=BOSS_DIA / 2.0,
        x_mm=-COLUMN_X,
        y_mm=BOSS_TOP_Y,
        label="front-left boss top rim",
        prefer="front",
    )
    boss_bottom = _circle_edge(
        front_circles,
        radius_mm=BOSS_DIA / 2.0,
        x_mm=-COLUMN_X,
        y_mm=BOSS_BOTTOM_Y,
        label="front-left boss bottom rim",
        prefer="front",
    )
    rail_top = _line_edge(front_lines, label="rail top face edge", along="x", y_mm=HALF_H)
    web_bottom = _line_edge(
        front_lines, label="web bottom edge", along="x", y_mm=-HALF_H
    )
    flange_underside = _line_edge(
        front_lines, label="flange underside edge", along="x", y_mm=FLANGE_BOT_Y
    )
    _dimension_entities(
        adapter,
        front,
        (boss_bottom, boss_top),
        text_xy=STACK_TEXT_XY,
        orientation="vertical",
        label="boss stack height",
    )
    _dimension_entities(
        adapter,
        front,
        (rail_top, boss_top),
        text_xy=BOSS_ABOVE_TEXT_XY,
        orientation="vertical",
        label="boss proud of the rail top",
    )
    _dimension_entities(
        adapter,
        front,
        (web_bottom, rail_top),
        text_xy=RING_TEXT_XY,
        orientation="vertical",
        label="rail band height",
    )
    _dimension_entities(
        adapter,
        front,
        (flange_underside, rail_top),
        text_xy=FLANGE_TEXT_XY,
        orientation="vertical",
        label="top flange height",
    )
    side_tap = _circle_edge(
        front_circles,
        radius_mm=SIDE_TAP_DIA / 2.0,
        x_mm=-COLUMN_X,
        y_mm=0.0,
        label="front-left side-screw tap",
        prefer="front",
    )
    # Hole Wizard callout: thread, class and depth are native (2X per feature).
    add_native_hole_callout(
        adapter,
        front,
        callout_xy=SIDE_TAP_CALLOUT_XY,
        label="side-screw taps",
        edge=side_tap,
    )

    # SECTION A-A: the rails' T-section (the web sits under the flange in the
    # plan and behind the front rail in the elevation, so only a cut shows
    # it).  Cut faces are section-generated entities: locate the four named
    # vertical edges in model space, then select the concrete entities through
    # IView instead of asking sheet-coordinate selection to infer them.
    section = create_section_view(
        adapter,
        top,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(1, 4),
        label="rail T-section",
    )
    _section_circles, section_lines = _view_edges(adapter, section)
    web_inner = _line_edge(
        section_lines,
        label="section +X web inner edge",
        along="y",
        x_mm=WEB_IN_X,
        z_mm=SECTION_CUT_Z,
    )
    web_outer = _line_edge(
        section_lines,
        label="section +X web outer edge",
        along="y",
        x_mm=WEB_OUT_X,
        z_mm=SECTION_CUT_Z,
    )
    _dimension_entities(
        adapter,
        section,
        (web_inner, web_outer),
        text_xy=WEB_TEXT_XY,
        label="web thickness",
        orientation="horizontal",
    )
    rail_inner = _line_edge(
        section_lines,
        label="section +X flange inner edge",
        along="y",
        x_mm=INNER_X,
        z_mm=SECTION_CUT_Z,
    )
    rail_outer = _line_edge(
        section_lines,
        label="section +X flange outer edge",
        along="y",
        x_mm=OUTER_X,
        z_mm=SECTION_CUT_Z,
    )
    _dimension_entities(
        adapter,
        section,
        (rail_inner, rail_outer),
        text_xy=SIDE_RAIL_TEXT_XY,
        label="side rail width",
        orientation="horizontal",
    )

    # Keep the process block below the plan's lowest boss, center marks and
    # projected leaders instead of letting those lines strike through it.
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, 0.090, char_height=0.0025
    )
    add_property_linked_note(adapter, "Top View Note", *TOP_VIEW_NOTE_XY)
    add_property_linked_note(
        adapter, "Front View Note", *FRONT_VIEW_NOTE_XY, char_height=0.0025
    )

    # Curating marked dimensions and inserting the hole table can materialize
    # Hole Wizard's redundant descriptive notes after the views are placed.
    # Remove them only after every annotation has been created so the table's
    # A3/A4 rows cannot be overprinted by "#10-24 Tapped Hole".
    removed_tap_notes = remove_notes_matching(adapter, "Tapped Hole")
    _telemetry.info(
        f"removed {removed_tap_notes} redundant automatic tapped-hole note(s)"
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Top Frame Ring Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
