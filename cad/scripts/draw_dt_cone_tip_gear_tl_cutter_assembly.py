r"""Create the T006 fly cutter's fitter sheet (MHA-DT-37-TL-00).

Issue #2358: the bar (item 1, MHA-DT-37-TL-02), the DT6-FORM1 bit (item 2,
MHA-DT-37-TL-01) and the bought set screw (item 3, MHA-SH-VN-54) as set up.
One sheet: the front view (the bit's face toward the viewer, so the face leads
with the spindle in forward) with items 1 and 2 ballooned and the stick-out
and swing radius as references measured off the model; the bottom view (the
cutting end, end-on) with item 3 ballooned; the shaded isometric; the BOM; the
three fitting steps.  Poses, the stick-out window and the step text come from
``dt_cone_tip_gear_tl_cutter_spec``; this recipe only lays the sheet out and
never edits the source assembly.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

import _config
import _telemetry
import dt_cone_tip_gear_tl_cutter_spec as fixture
from _check import check
from _com import _early_bound
from _drawing_balloons import (
    BalloonAnchor,
    add_component_bom_balloons,
    assert_balloon_landings,
)
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
)
from _drawing_dimensions import set_reference_dimension
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_tables import insert_bom_table
from _drawing_types import DrawingLayout
from _drawing_view_configuration import (
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
)
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    place_view,
    view_name,
    visible_component_entities,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["dt_cone_tip_gear_tl_cutter_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the fly-cutter sheet must remain landscape")

DRAWING_NUMBER = fixture.DRAWING_NUMBER
# A Ø.375 x 1.75 bar with a .10 stick-out: 3:1 prints the stick-out 7.6 mm.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
ISO_SCALE = (2, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
# The bar's cutting-end centre (the assembly origin) on the front view, the
# bar standing up from it; the bottom view projected below; the isometric in
# the middle column; the BOM and the steps in the right half, above the title
# block (x >= 0.216 m, y <= 0.066 m).
FRONT_ORIGIN = (0.080, 0.090)
BOTTOM_ORIGIN = (FRONT_ORIGIN[0], 0.040)
ISO_CENTER = (0.165, 0.150)
ISO_NOTE_XY = (0.135, 0.080)
BOM_ANCHOR = (0.219, 0.262)
STEPS_XY = (0.219, 0.215)
BALLOON_MARGIN = 0.012

BAR, BIT, SET_SCREW = fixture.BAR, fixture.BIT, fixture.SET_SCREW
BOM_COMPONENTS = fixture.BOM_COMPONENTS
BOM_ITEMS = fixture.BOM_ITEMS
# Literal rows, so this sheet re-keys only on its own three parts.
_ROWS = {
    BAR: _config.parts("dt-cone-tip-gear-tl-cutter-bar"),
    BIT: _config.parts("dt-cone-tip-gear-tl-form-cutter"),
    SET_SCREW: _config.parts("sh-vn-arbor-set-screw"),
}
if tuple(_ROWS) != BOM_COMPONENTS:
    raise AssertionError("the fly-cutter rows are its BOM components, in order")
BOM_DESCRIPTIONS = {stem: str(row["title"]).upper() for stem, row in _ROWS.items()}
PART_NUMBERS = {stem: str(row["number"]) for stem, row in _ROWS.items()}
BOM_COMPONENT_IDENTITIES: dict[str, tuple[str, str | None]] = {
    stem: (stem, None) for stem in BOM_COMPONENTS
}
BALLOON_ANCHORS = {stem: BalloonAnchor() for stem in BOM_COMPONENTS}
# Items 1 and 2 balloon in the front view; item 3, inside item 1's tap, shows
# only end-on in the bottom view.
FRONT_ITEMS = (BAR, BIT)
BOTTOM_ITEMS = (SET_SCREW,)
if set(FRONT_ITEMS) | set(BOTTOM_ITEMS) != set(BOM_COMPONENTS):
    raise AssertionError("every BOM row is ballooned once")

# --- The references, measured off the model in the front view -------------------
_BAR_R = fixture.bar.BAR_RADIUS
_STATION = fixture.bar.CROSS_HOLE_STATION
# The bar's right silhouette, picked well above the cross hole.
SILHOUETTE_PICK = (
    FRONT_ORIGIN[0] + _BAR_R * _S,
    FRONT_ORIGIN[1] + (_STATION + 12.0) * _S,
)
# The bar's axis as an owned centreline, end to end with a short overrun.
AXIS_ENDS_MM = ((0.0, -2.0, 0.0), (0.0, fixture.bar.BAR_LENGTH + 2.0, 0.0))
STICK_OUT_TEXT_XY = (
    FRONT_ORIGIN[0] + (_BAR_R + fixture.STICK_OUT / 2.0) * _S,
    FRONT_ORIGIN[1] + (_STATION + 6.0) * _S,
)
SWING_TEXT_XY = (
    FRONT_ORIGIN[0] + fixture.SWING_RADIUS / 2.0 * _S,
    FRONT_ORIGIN[1] + (_STATION + 11.0) * _S,
)
CALLOUT_ABOVE = 3  # swDimensionTextCalloutAbove
# The bit's tip corner in its own frame (mm): the root arc's end on the face
# (y = 0) where the upper relief starts, .0004 ahead of P1 -- below the
# references' three places, so they print the spec's stick-out and radius.
_FORM = {segment.name: segment for segment in fixture.bit.form_segments(1.0)}
_CORNER_X, _CORNER_Z = fixture.bit.face_point(*_FORM["RootArc"].point(0.0))
TIP_CORNER_MM = (_CORNER_X, 0.0, _CORNER_Z)


def _add_note(adapter: Any, text: str, xy: tuple[float, float], *, label: str) -> None:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the fly-cutter {label}")
    printed = (
        str(_early_bound(note, "INote").GetText() or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    if printed != text:
        raise RuntimeError(f"fly-cutter {label} printed as {printed!r}")


def _bom_items(adapter: Any, table: Any) -> dict[str, str]:
    """Each part's ITEM NO. as the BOM prints it, read off its PART NUMBER
    row; the steps cite items 1-3."""
    table = _early_bound(table, "ITableAnnotation")

    def cell(row: int, column: int) -> str:
        return str(
            adapter._attempt(lambda: table.DisplayedText2(row, column, True)) or ""
        ).strip()

    header = [cell(0, column).upper() for column in range(int(table.ColumnCount))]
    items = [index for index, text in enumerate(header) if text.startswith("ITEM NO")]
    numbers = [index for index, text in enumerate(header) if text == "PART NUMBER"]
    if (
        int(table.RowCount) != 1 + len(BOM_COMPONENTS)
        or len(items) != 1
        or len(numbers) != 1
    ):
        raise RuntimeError(
            f"fly-cutter BOM is not {len(BOM_COMPONENTS)} item rows: {header!r}"
        )
    stems = {number: stem for stem, number in PART_NUMBERS.items()}
    printed = {
        stems.get(cell(row, numbers[0]), cell(row, numbers[0])): cell(row, items[0])
        for row in range(1, int(table.RowCount))
    }
    if printed != BOM_ITEMS:
        raise RuntimeError(
            f"fly-cutter BOM numbers its parts {printed!r}, not {BOM_ITEMS!r}"
        )
    return printed


def _move_model_point(
    adapter: Any,
    view: Any,
    point_mm: tuple[float, float, float],
    target: tuple[float, float],
    *,
    label: str,
) -> None:
    """Move ``view`` so the model point lands on ``target`` (sheet m)."""
    view = _early_bound(view, "IView")
    point = tuple(value / 1000.0 for value in point_mm)
    here = model_points_in_view(adapter, view, [point], label=label)[0]
    position = tuple(float(value) for value in view.Position)
    moved = [position[i] + target[i] - here[i] for i in range(2)]
    if not view.SetViewPosition(double_array(moved), False):
        raise RuntimeError(f"failed to move the {label}")
    rebuild_drawing(adapter, label=f"place {label}")
    here = model_points_in_view(adapter, view, [point], label=label)[0]
    if math.dist(here, target) > 1e-4:
        raise RuntimeError(f"{label}: origin sits at {here!r}, not {target!r}")


def _tip_corner(view: Any) -> Any:
    """The bit's tip corner on its face: the vertex where the root arc meets
    the upper relief, which the references end on.

    The root arc is not a circular edge: the bit's form is cut from native
    equation curves (``_gear.equation_curve``, an equation-driven spline), so
    every form edge on the face is a B-spline and ``ICurve.IsCircle`` is false
    for all of them (farm run 20261112T203021325Z). A linear dimension cannot
    end on a spline at P1; the corner is a true vertex of the face loop.
    Vertices read in the bit's own frame, so the bit's are matched by stem."""
    view = _early_bound(view, "IView")
    target = TIP_CORNER_MM
    matches = []
    for raw_component in view.GetVisibleComponents() or ():
        component = _early_bound(raw_component, "IComponent2")
        if Path(str(component.GetPathName() or "")).stem.casefold() != BIT:
            continue
        for raw in visible_component_entities(view, component, 1):
            edge = _early_bound(raw, "IEdge")
            for raw_vertex in (edge.GetStartVertex(), edge.GetEndVertex()):
                if raw_vertex is None:
                    continue
                vertex = _early_bound(raw_vertex, "IVertex")
                point = tuple(float(value) * 1000.0 for value in vertex.GetPoint())
                if math.dist(point, target) < 1e-4:
                    matches.append(vertex)
    if not matches:
        raise RuntimeError(
            f"fly-cutter front view shows no bit vertex at the tip corner {target!r} mm"
        )
    return matches[0]


def _axis_centreline(adapter: Any, view: Any) -> Any:
    """The bar's axis, one owned centreline in the view's sketch
    (draw_fr_top_frame._add_view_centerlines), returned as its segment."""
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the fly-cutter front view")
    draw.ClearSelection2(True)
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    ends = []
    for x, y in model_points_in_view(
        adapter,
        view,
        [tuple(value / 1000.0 for value in end) for end in AXIS_ENDS_MM],
        label="bar axis endpoints",
    ):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        ends.append(
            tuple(
                _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
            )
        )
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateCenterLine(*ends[0], *ends[1])
    finally:
        manager.AddToDB = previous
    if segment is None:
        raise RuntimeError("failed to create the bar's axis centreline")
    segment = _early_bound(segment, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="bar axis centreline")
    return segment


def _reference(
    adapter: Any,
    view: Any,
    *,
    label: str,
    expected_mm: float,
    callout: str,
    text_xy: tuple[float, float],
    entity_types: tuple[str, str],
    entities: tuple[Any | None, Any | None],
    p0: tuple[float, float],
) -> Any:
    """One horizontal reference to the tip, proved against the spec's value,
    parenthesized, at the spec's places, its name above it."""
    display = add_edge_dimension(
        adapter,
        view,
        p0=p0,
        p1=(0.0, 0.0),
        text_xy=text_xy,
        label=label,
        orientation="horizontal",
        entity_types=entity_types,
        entities=entities,
    )
    display = _early_bound(display, "IDisplayDimension")
    measured = abs(
        float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue)
    )
    if abs(measured * 1000.0 - expected_mm) > 1e-3:
        raise RuntimeError(
            f"{label} measured {measured * 1000.0:.4f} mm, expected {expected_mm:.4f}"
        )
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(fixture.DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != fixture.DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")
    display.SetText(CALLOUT_ABOVE, callout)
    if str(display.GetText(CALLOUT_ABOVE) or "") != callout:
        raise RuntimeError(f"{label} callout did not persist")
    return display


def _place_sheet(adapter: Any) -> Any:
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_ORIGIN, scale=VIEW_SCALE)
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_ORIGIN, scale=VIEW_SCALE
    )
    origin = (0.0, 0.0, 0.0)
    _move_model_point(
        adapter, front, origin, FRONT_ORIGIN, label="fly-cutter front view"
    )
    _move_model_point(
        adapter, bottom, origin, BOTTOM_ORIGIN, label="fly-cutter bottom view"
    )
    for view, name in ((front, "*Front"), (bottom, "*Bottom")):
        set_hidden_lines_removed(adapter, view)
        apply_view_configuration(adapter, view, label=f"fly cutter {name}")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_high_quality_shaded_with_edges(adapter, iso, label="fly cutter isometric")
    apply_view_configuration(
        adapter, iso, role=ViewRole.FULL_DETAIL, label="fly cutter *Isometric"
    )
    assert_full_detail_view(adapter, label="fly cutter")

    table = insert_bom_table(
        adapter,
        front,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        component_identities=BOM_COMPONENT_IDENTITIES,
        part_number_property="Number",
        label="fly cutter",
    )
    items = _bom_items(adapter, table)
    landings = []
    for view, stems, label in (
        (front, FRONT_ITEMS, "fly-cutter front balloons"),
        (bottom, BOTTOM_ITEMS, "fly-cutter bottom balloons"),
    ):
        landings += add_component_bom_balloons(
            adapter,
            view,
            items=tuple((stem, items[stem]) for stem in stems),
            anchors=BALLOON_ANCHORS,
            label=label,
            margin=BALLOON_MARGIN,
            explode_offsets={},
        )
    if len(landings) != len(BOM_COMPONENTS):
        raise RuntimeError(
            f"fly cutter carries {len(landings)} balloons, expected {len(BOM_COMPONENTS)}"
        )

    # The setting the fitter makes and the radius it gives, both off the bit's
    # tip corner on its face (a vertex; see _tip_corner).
    tip = _tip_corner(front)
    _reference(
        adapter,
        front,
        label="stick-out",
        expected_mm=fixture.STICK_OUT + TIP_CORNER_MM[0],
        callout=fixture.STICK_OUT_CALLOUT,
        text_xy=STICK_OUT_TEXT_XY,
        entity_types=("SILHOUETTE", "VERTEX"),
        entities=(None, tip),
        p0=SILHOUETTE_PICK,
    )
    axis = _axis_centreline(adapter, front)
    _reference(
        adapter,
        front,
        label="swing radius",
        expected_mm=fixture.SWING_RADIUS + TIP_CORNER_MM[0],
        callout=fixture.SWING_RADIUS_CALLOUT,
        text_xy=SWING_TEXT_XY,
        entity_types=("SKETCHSEGMENT", "VERTEX"),
        entities=(axis, tip),
        p0=(0.0, 0.0),
    )
    for text, xy, label in (
        (fixture.ASSEMBLY_STEPS, STEPS_XY, "fitting steps"),
        (fixture.ISO_NOTE, ISO_NOTE_XY, "isometric scale note"),
    ):
        _add_note(adapter, text, xy, label=label)
    set_hidden_lines_removed(adapter, front)
    return lambda: assert_balloon_landings(adapter, landings)


@_telemetry.traced("drawing.dt_cone_tip_gear_tl_cutter_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open fly-cutter drawing source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        _early_bound(adapter.currentModel, "IModelDoc2"),
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    if properties["Number"] != DRAWING_NUMBER:
        raise RuntimeError(
            f"fly-cutter source Number {properties['Number']!r} != {DRAWING_NUMBER!r}"
        )
    new_project_drawing(
        adapter,
        layout=SPEC.layout,
        scale=SHEET_SCALE,
        unit=fixture.CONTRACT.drawing_unit,
    )
    settled = _place_sheet(adapter)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Cone Tip Gear Fly Cutter Assembly Drawing",
        scale=SHEET_SCALE,
        settled_checks=(settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
