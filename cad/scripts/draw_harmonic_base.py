r"""Create the curated machinist drawing for the two-plate harmonic base.

The SLDPRT remains authoritative.  This recipe supplies only the base's views,
plate dimensions, the mounting-hole table, and manufacturing notes; every
shared sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The base is machined from one-piece gray-iron stock: the legacy lower flange and
upper pad retain their front edges and extend 35.415 mm rearward, with four counterbored
lag-screw mounting holes, and nine assembly-drilled hardware seats.  The plate
is 457 mm long, so the whole sheet runs 1:2; the front elevation drops to 1:4.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
machined base carries no datums or frames; the native hole table gives every
station under the title block's general tolerance.  The plan carries both
plate footprints (marked), the rim width and the three concentric plan-corner
radii; the front elevation carries the flange and pad thicknesses (marked),
the reveal and overall height, with the deck depth stated beside the view.

Run with SolidWorks open::

    uv run python cad\scripts\draw_harmonic_base.py harmonic-base
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    insert_hole_table,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_harmonic_base import (
    BLOCK_SCREW_HOLE_DIA,
    BLOCK_SCREW_XZ,
    CBORE_DIA,
    FLANGE_CORNER_R,
    FOOT_SCREW_HOLE_DIA,
    FOOT_SCREW_XZ,
    HOLE_DIA,
    HOLE_XZ,
    NAMEPLATE_SCREW_HOLE_DIA,
    NAMEPLATE_SCREW_XZ,
    PAD_CORNER_R,
    PIVOT_SCREW_HOLE_DIA,
    PIVOT_SCREW_XZ,
    RIM_INNER_R,
    STOP_SCREW_HOLE_DIA,
    STOP_SCREW_XZ,
)
from harmonic_base_spec import (
    BOTTOM_FRONT_Z,
    BOTTOM_LENGTH,
    BOTTOM_REAR_Z,
    BOTTOM_THICKNESS,
    BOTTOM_WIDTH,
    LIP_W,
    RIM_TOP,
    STACK_HEIGHT,
    TOP_LENGTH,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["harmonic_base"]
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

SHEET_SCALE = (1.0, 2.0)  # 1:2 whole sheet (457 mm plate)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 0.5 plan/front sheet-metres-per-mm
SIDE_SCALE = 0.25  # the 1:4 front elevation

if abs((BOTTOM_REAR_Z - BOTTOM_FRONT_Z) - BOTTOM_WIDTH) > 1e-12:
    raise AssertionError("base drawing extents disagree with the overall depth")

# Sheet layout (meters).  The plan (top) carries the footprint + the hole
# pattern; the front elevation (1:4) shows the stepped stack; the hole
# table sits upper-right and the notes fill the lower-left.  The plan runs at the
# sheet's 1:2; only the 1:4 elevation carries a scale note.
TOP_CENTER = (0.130, 0.163)
SIDE_CENTER = (0.345, 0.075)
# The elevation is placed on its bounding box (y 0..RIM_TOP): model y 0 sits
# half the overall height below the view centre.
SIDE_BBOX_MID_Y = RIM_TOP / 2.0  # 26.65
# Straight plan runs end where the concentric corner arcs begin.
CORNER_CENTER_X = BOTTOM_LENGTH / 2.0 - FLANGE_CORNER_R  # 206.375
CORNER_CENTER_Z = BOTTOM_WIDTH / 2.0 - FLANGE_CORNER_R  # 117.475

if abs((TOP_LENGTH / 2.0 - PAD_CORNER_R) - CORNER_CENTER_X) > 1e-9:
    raise AssertionError("pad corner arcs are not concentric with the flange's")
if abs((TOP_LENGTH / 2.0 - LIP_W - RIM_INNER_R) - CORNER_CENTER_X) > 1e-9:
    raise AssertionError("rim inner corner arcs are not concentric with the flange's")


def _plan_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point for a plan station (machine X, Z in mm), top view."""
    return (
        TOP_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        TOP_CENTER[1] - z_mm * VIEW_SCALE / 1000.0,
    )


def _side_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point for a model (X, Y) in the 1:4 front elevation."""
    return (
        SIDE_CENTER[0] + x_mm * SIDE_SCALE / 1000.0,
        SIDE_CENTER[1] + (y_mm - SIDE_BBOX_MID_Y) * SIDE_SCALE / 1000.0,
    )


def _hole_rim(x_mm: float, z_mm: float, diameter_mm: float) -> tuple[float, float]:
    """Sheet pick on a plan-view hole rim, offset in machine +X."""
    return _plan_xy(x_mm + diameter_mm / 2.0, z_mm)


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position (meters).  Plan: the pad outline nearest the plate, the flange
# envelope outside it (smallest span nearest); the two vertical texts sit at
# different heights so their horizontal texts cannot touch.  Elevation: the
# flange and pad thicknesses stacked on the LEFT of the view, thinnest nearest.
TOP_KEEP = {
    "TopLen": (TOP_CENTER[0], 0.2428),
    "BottomLen": (TOP_CENTER[0], 0.2518),
    "TopWid": (0.2513, 0.150),
    "BottomWid": (0.2643, 0.178),
}
SIDE_KEEP = {
    "FlangeT": (0.280, _side_xy(0.0, BOTTOM_THICKNESS / 2.0)[1]),  # y 0.0699
    "PadT": (0.272, _side_xy(0.0, STACK_HEIGHT - 8.0)[1]),  # y 0.0790
}
# Drawing dimensions (text positions, sheet metres).
OVERALL_TEXT_XY = (0.264, 0.0745)  # (53.30) reference, left of the elevation
# The deck is hidden behind the front rim wall, and its derived-view edge is
# not reliably selectable.  State the same spec-owned depth beside the view.
DECK_DEPTH_NOTE = f"DECK {RIM_TOP - STACK_HEIGHT:.2f} BELOW RIM TOP"
# Rim width and reveal chained above the plan's NE corner on one line: the
# 7.00 spans rim inner edge -> pad edge (text outside, left), the (6.35)
# reference spans pad edge -> flange edge (text outside, right), sharing the
# pad edge's extension line with TopLen and the flange's with BottomLen.
RIM_WIDTH_TEXT_XY = (0.229, 0.2360)
REVEAL_TEXT_XY = (0.2515, 0.2360)
FLANGE_RADIUS_TEXT_XY = (0.2555, 0.2270)  # R22.23 at the NE corner arc
PAD_RADIUS_TEXT_XY = (0.2555, 0.0880)  # R15.88 at the SE corner arc
RIM_RADIUS_TEXT_XY = (0.2470, 0.0790)  # R8.88 at the SE corner arc

# Hole-table origin corner (the plate's lower-left plan corner) + the four
# mounting-hole rim picks, all in sheet meters.  The native table reads each
# hole's real Ø13 THRU / counterbore callout and its X/Y station from the datum.
_DATUM_XY = (
    TOP_CENTER[0] - BOTTOM_LENGTH * VIEW_SCALE / 2000.0,
    TOP_CENTER[1] - BOTTOM_REAR_Z * VIEW_SCALE / 1000.0,
)
HOLE_TABLE_ANCHOR = (0.274, 0.256)
SIDE_VIEW_NOTE_XY = (0.260, 0.098)
DECK_DEPTH_NOTE_XY = (SIDE_CENTER[0], SIDE_VIEW_NOTE_XY[1])


ALL_HOLES = (
    *((x, z, HOLE_DIA) for x, z in HOLE_XZ),
    (*PIVOT_SCREW_XZ, PIVOT_SCREW_HOLE_DIA),
    (*STOP_SCREW_XZ, STOP_SCREW_HOLE_DIA),
    *((x, z, BLOCK_SCREW_HOLE_DIA) for x, z in BLOCK_SCREW_XZ),
    *((x, z, FOOT_SCREW_HOLE_DIA) for x, z in FOOT_SCREW_XZ),
    # Appended LAST so hole_entities[8] (the tapped-position FCF's block-hole
    # anchor) keeps its index.
    *((x, z, NAMEPLATE_SCREW_HOLE_DIA) for x, z in NAMEPLATE_SCREW_XZ),
)


def _view_edges(
    adapter: Any, view: Any
) -> tuple[list[tuple[float, float, float, float, Any]], list[tuple[tuple[float, ...], Any]]]:
    """Every model edge shown in ``view`` (hidden lines included).

    Returns ``(circles, lines)``: circles as ``(cx, cy, cz, radius, edge)`` and
    lines as ``(LineParams, edge)``, all in model metres.  Topological picks
    keep every dimension off the sheet-coordinate tolerance: the plate rims'
    chamfer edges and the pad root fillet's tangent edges all lie within a
    millimetre of the edges the print dimensions.
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

    ``LineParams`` is ``(point xyz, direction xyz)``; an edge matches when its
    direction is the requested axis and its point lies on every axis station
    given.  Coincident candidates (both ends of a face, the deck's front and
    rear edges) project to the same sheet line; the top-most is taken so a
    plan pick lands on the visible rim, never on a hidden one below it.
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
            f"harmonic-base view has no straight edge for {label} "
            f"(along {along}, x={x_mm!r}, y={y_mm!r}, z={z_mm!r})"
        )
    matches.sort(key=lambda item: -item[0])
    return matches[0][1]


def _corner_arc(
    circles: list[tuple[float, float, float, float, Any]],
    *,
    radius_mm: float,
    x_sign: float,
    z_sign: float,
    label: str,
) -> Any:
    """The top-most plan-corner arc of ``radius_mm`` at one concentric corner."""
    matches = [
        (cy, edge)
        for cx, cy, cz, radius, edge in circles
        if abs(radius - radius_mm / 1000.0) <= 5e-5
        and abs(cx - x_sign * CORNER_CENTER_X / 1000.0) <= 5e-5
        and abs(cz - z_sign * CORNER_CENTER_Z / 1000.0) <= 5e-5
    ]
    if not matches:
        raise RuntimeError(
            f"harmonic-base plan has no R{radius_mm:g} corner arc for {label}"
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
    creates the dimension with its text at ``text_xy`` (sheet metres).  A
    single arc selected with ``"smart"`` yields its radius dimension.
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


def _reference(adapter: Any, dimension: Any, *, label: str) -> Any:
    """Parenthesize a drawing-added dimension (ASME reference notation)."""
    # Add*Dimension2 hands back the IDisplayDimension (late-bound); bind it
    # before reading the IAnnotation the reference helper wants.
    return set_reference_dimension(
        adapter,
        _early_bound(dimension, "IDisplayDimension").GetAnnotation(),
        label=label,
    )


def _visible_hole_table_entities(
    adapter: Any, view: Any
) -> tuple[tuple[Any, ...], Any, Any]:
    """Return hole rims and the rear/left outer edges in the top view.

    The plan corners are broken (CornerFillets R3.18), so no corner vertex
    exists to anchor the hole table; the caller passes the two outer edges as
    ``datum_axes`` and the table origin lands on their VIRTUAL intersection --
    the theoretical sharp corner every LOC value is measured from.
    """
    circles, lines = _view_edges(adapter, view)

    visible_counterbores = [
        (x_mm, z_mm)
        for x_mm, z_mm in HOLE_XZ
        if any(
            abs(x - x_mm / 1000.0)
            + abs(z - z_mm / 1000.0)
            + abs(radius - CBORE_DIA / 2000.0)
            <= 5e-5
            for x, _y, z, radius, _edge in circles
        )
    ]
    # With hidden lines shown in the plan view (drawing-simplicity-policy.md
    # rule 7) the underside counterbore rims are legitimately reported; the
    # radius-keyed match below (5e-5 m on a 5 mm radius difference) cannot
    # confuse them with the through-hole rims, so this is a debug fact, not
    # the hard failure it was under hidden-lines-removed.
    if visible_counterbores:
        _telemetry.debug(
            f"counterbore rims reported in the plan view: {visible_counterbores!r}"
        )

    selected_edges: list[Any] = []
    used: set[int] = set()
    for x_mm, z_mm, diameter_mm in ALL_HOLES:
        expected = (
            x_mm / 1000.0,
            z_mm / 1000.0,
            diameter_mm / 2000.0,
        )
        candidates = sorted(
            (
                abs(x - expected[0]) + abs(z - expected[1]) + abs(radius - expected[2]),
                index,
                edge,
            )
            for index, (x, _y, z, radius, edge) in enumerate(circles)
            if index not in used
        )
        if not candidates or candidates[0][0] > 5e-5:
            nearest = candidates[0][0] if candidates else None
            raise RuntimeError(
                "harmonic-base plan has no visible circular rim for hole "
                f"({x_mm:g}, {z_mm:g}) diameter {diameter_mm:g} mm; "
                f"nearest error={nearest!r} m"
            )
        _, index, edge = candidates[0]
        used.add(index)
        selected_edges.append(edge)

    rear_edge = _line_edge(
        lines, label="rear outer edge", along="x", z_mm=BOTTOM_REAR_Z
    )
    left_edge = _line_edge(
        lines, label="left outer edge", along="z", x_mm=-BOTTOM_LENGTH / 2.0
    )

    return (tuple(selected_edges), rear_edge, left_edge)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open harmonic-base source", await adapter.open_model(str(SOURCE)))
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
            "Side View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Side View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Harmonic Base Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "harmonic base; stepped; gray iron stock",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently auto-scale,
    # which shifts every coordinate-based pick on it.
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=(1, 4))
    # Hidden lines ON in every orthographic view: the plan shows the underside
    # counterbores and the blind seats' depths, the elevation the hole depths.
    for view in (top, side):
        set_hidden_lines_visible(adapter, view)

    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    curate_view_dimensions(adapter, side, keep=SIDE_KEEP, view_label="side")
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the base hole pattern")

    hole_entities, rear_edge, left_edge = _visible_hole_table_entities(
        adapter, top
    )

    # One complete hole table: four underside counterbores followed by every
    # top-side blind swing/pinion seat, every station under the title-block
    # tolerance (ordinary X LOC / Y LOC headers, no position frame to feed).
    insert_hole_table(
        adapter,
        top,
        datum_xy=_DATUM_XY,
        hole_points=tuple(_hole_rim(x, z, diameter) for x, z, diameter in ALL_HOLES),
        datum_axes=(rear_edge, left_edge),
        hole_entities=hole_entities,
        # Every printed LOC is re-derived from the shared stations: X from the
        # left end (x = -L/2), Y from the rear face (z = +W/2) -- proven
        # against the seat (A1 stop, B1 pivot, E1-E4 lags all exact).
        expected_locations_mm=tuple(
            (x + BOTTOM_LENGTH / 2.0, BOTTOM_WIDTH / 2.0 - z)
            for x, z, _diameter in ALL_HOLES
        ),
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="harmonic-base mounting",
    )

    # Plan: the rim width between the pad's right edge and the rim's inner
    # edge (text outside, left of the pad's extension line so no dimension
    # line sits under the TopLen/BottomLen extension lines), and the three
    # concentric corner radii on the two corners with sheet room outside the
    # plate (each text inside its arc's own quadrant, distinct angles).
    plan_circles, plan_lines = _view_edges(adapter, top)
    pad_right = _line_edge(
        plan_lines, label="pad right edge", along="z", x_mm=TOP_LENGTH / 2.0
    )
    rim_inner_right = _line_edge(
        plan_lines,
        label="rim inner right edge",
        along="z",
        x_mm=TOP_LENGTH / 2.0 - LIP_W,
    )
    _dimension_entities(
        adapter,
        top,
        (rim_inner_right, pad_right),
        text_xy=RIM_WIDTH_TEXT_XY,
        orientation="horizontal",
        label="rim width",
    )
    # The reveal off the flange end, chained onto the rim width (reference:
    # the pad outline is the controlling size, note 1 centres it).  Picked in
    # the plan on the chamfers' lower edges -- the elevation's end faces are
    # bounded only by tangent edges to the corner fillets.
    flange_right = _line_edge(
        plan_lines, label="flange right edge", along="z", x_mm=BOTTOM_LENGTH / 2.0
    )
    reveal = _dimension_entities(
        adapter,
        top,
        (pad_right, flange_right),
        text_xy=REVEAL_TEXT_XY,
        orientation="horizontal",
        label="pad reveal reference",
    )
    _reference(adapter, reveal, label="pad reveal reference")
    _dimension_entities(
        adapter,
        top,
        (
            _corner_arc(
                plan_circles,
                radius_mm=FLANGE_CORNER_R,
                x_sign=1.0,
                z_sign=-1.0,
                label="flange NE corner",
            ),
        ),
        text_xy=FLANGE_RADIUS_TEXT_XY,
        orientation="smart",
        label="flange corner radius",
    )
    _dimension_entities(
        adapter,
        top,
        (
            _corner_arc(
                plan_circles,
                radius_mm=PAD_CORNER_R,
                x_sign=1.0,
                z_sign=1.0,
                label="pad SE corner",
            ),
        ),
        text_xy=PAD_RADIUS_TEXT_XY,
        orientation="smart",
        label="pad corner radius",
    )
    _dimension_entities(
        adapter,
        top,
        (
            _corner_arc(
                plan_circles,
                radius_mm=RIM_INNER_R,
                x_sign=1.0,
                z_sign=1.0,
                label="rim inner SE corner",
            ),
        ),
        text_xy=RIM_RADIUS_TEXT_XY,
        orientation="smart",
        label="rim inner corner radius",
    )

    # Elevation: the overall height (reference: flange + pad + rim).  The deck
    # plane is hidden behind the front rim wall and is not a reliable
    # derived-view selection, so its spec-owned depth is stated beside the
    # elevation rather than guessed from another edge.
    _side_circles, side_lines = _view_edges(adapter, side)
    underside = _line_edge(side_lines, label="underside edge", along="x", y_mm=0.0)
    rim_top = _line_edge(side_lines, label="rim top edge", along="x", y_mm=RIM_TOP)
    overall = _dimension_entities(
        adapter,
        side,
        (underside, rim_top),
        text_xy=OVERALL_TEXT_XY,
        orientation="vertical",
        label="overall height reference",
    )
    _reference(adapter, overall, label="overall height reference")
    if add_note(adapter, DECK_DEPTH_NOTE, *DECK_DEPTH_NOTE_XY) is None:
        raise RuntimeError("failed to add harmonic-base deck-depth note")

    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, 0.075, char_height=0.0025
    )
    add_property_linked_note(adapter, "Side View Note", *SIDE_VIEW_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Harmonic Base Manufacturing Drawing",
        scale=SHEET_SCALE,
        # Both curated views delete their unnamed Hole Wizard callouts during
        # model-item import.  Keep this matcher as a zero-tolerance guard: if
        # current view generation ever leaks a generic callout again,
        # finalize_drawing removes it and fails because its default expected
        # count is zero.
        redundant_note_substrings=("Tapped Hole",),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
