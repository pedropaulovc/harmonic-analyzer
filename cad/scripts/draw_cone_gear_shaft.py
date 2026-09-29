r"""Create the cone-gear-shaft manufacturing drawing under the simplicity policy.

The turned shaft is shown horizontally at 1:1 with baseline lengths from the
collar's thrust face below it and every diameter above it on that same side
view, each dimension line inside the land it measures (the 3.2 mm collar
instead takes one near-side arrow on its rim).  The two short lands
ahead of the tip are 6.9 mm long, so the three tip-end diameter texts climb
in steps: the tip's line rises highest and each text hangs to the RIGHT of
its line above every line it spans.  Each gear land's D-flat is shown in its
own enlarged cut-only section, A-A to D-D, carrying its across-flat.  A
standard isometric supplies pictorial clarity, and the note names the bores
the seats and flats mate and the tailstock support the tip land needs
(U40).  Source geometry and native model fits stay authoritative: the sheet
types no tolerance and no precision.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_gear_shaft.py cone-gear-shaft
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any, NamedTuple

from collections.abc import Mapping, Sequence

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_annotation_extent import (
    CLEAR_GAP_M,
    PLACE_SETTLE_M,
    Box,
    callout_ink,
    gdt_box,
    move_annotation,
    require_clear,
    require_inside,
    require_leader_clear,
    sheet_region,
)
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    add_surface_finish,
    create_section_view,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
    visible_view_entities,
)
from _drawing_leaders import (
    Segment,
    dimension_segments,
    dimension_text_points,
    distance_to_box,
    leader_segments,
    set_near_side_diameter,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import estimate_text_box
from _surface_finish import surface_finish_by_key
from cone_gear_shaft_spec import (
    COLLAR_DIA,
    COLLAR_STOCK_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_REFERENCE_PRECISION,
    FILLET_CALLOUT,
    FLAT_LANDS,
    JOURNAL_DIA,
    SECTION_DIAS,
    SHAFT_LENGTH,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    delete_view,
    iter_views,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_gear_shaft"]
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

SHEET_SCALE = (1.0, 1.0)
SIDE_SCALE = (1, 1)
ISO_SCALE = (1, 2)


# Landscape sheet, 0.4318 x 0.2794 m, title block bottom right (x > ~0.216,
# y < ~0.066).  The 199.34 mm shaft at 1:1 spans 0.0533..0.2526, leaving the
# right third for the pictorial and the four D sections; the group sits just
# below mid-height so the baseline stack below and the diameters above share
# the field with the note block in the lower left (review 2026-09-23: at
# 0.170 rows A-B stood empty but for the note).  The view is placed by its
# large end: every dimension below is laid out from that datum face, so a
# change at the tip (the 2026-09-28 tip stack shortened it 1.55 mm) moves
# only the tip.
BIG_END_X = 0.2526
SIDE_CENTER = (BIG_END_X - SHAFT_LENGTH / 2000.0, 0.150)
ISO_CENTER = (0.345, 0.165)
NOTES_XY = (0.058, 0.060)
# Off-sheet-left donor: the five diameters are model dimensions of circular
# profile sketches, so they can only be IMPORTED into a view that faces those
# circles.  They are imported here, dragged onto the shoulder each one
# belongs to, and this view is then deleted.
DONOR_CENTER = (0.360, 0.090)

# Lengths (option A, #914): ONE origin, the collar's thrust face at sheet x
# 0.2096.  Everything measured from it is baseline below the shaft, one tier
# per dimension, the shortest nearest the part: the collar web, the three
# land steps, then the tip (#917 R5 (a)).  Every tier is one line of text.
# The journal runs the other way from the same origin on the first tier, and
# the front-to-tip overall, a reference, hangs lowest, above the title block.
# A station's text is centred in its span when it fits there with
# STATION_TEXT_CLEARANCE to spare; the web's 3.18 span is narrower than its
# text, so the text stands LEFT of the collar's north witness line (the 916a
# render had the web text touch that line).  The one radius rides above the
# 3/8-to-1/4 in step it attaches to (the fillet's first edge), right of the
# Ø6.350 line.
SIDE_KEEP = {
    "CollarWidth": (0.1985, 0.1355),
    "Sec0End": (0.2311, 0.1355),
    "Sec1End": (0.1498, 0.1275),
    "Sec2End": (0.1464, 0.1195),
    "Sec3End": (0.1429, 0.1115),
    "Sec4End": (0.1314, 0.1035),
    "ShoulderR": (0.1000, 0.1640),
}
OVERALL_REFERENCE_TEXT_XY = (0.1515, 0.0795)
# Sheet width of one length digit or point at the dimension font (the 916a
# render measured "10.781" at 13.4 mm, 2.2 mm a character), and the ink every
# length text keeps from any extension line crossing its tier.
LENGTH_CHAR_WIDTH = 0.0023
STATION_TEXT_CLEARANCE = 0.002
# Diameters, imported on the donor and dragged onto the side view.  A vertical
# linear dimension's line sits at its text x and the text hangs to the RIGHT
# of that line (~32 mm wide with its stacked band), so each x lies INSIDE the
# land it measures (the big end is at sheet x 0.2526; land 1 spans
# 0.0900..0.2096, land 2 0.0831..0.0900, land 3 0.0762..0.0831, land 4
# 0.0533..0.0762); Ø12.231 stands just off the faced end.  Lands 2 and 3 are
# only 6.9 mm long, so a tip-end text spans its right-hand neighbours'
# lines: the tip's text sits highest and each neighbour to the right steps
# down, so no line rises through a text (codex, 18395f30).  Lands 2 and 3
# carry their lines mid-land; the tip's line stays 1.7 mm in from the tip
# face, right of the tip finish glyph.
SIDE_DIAMETERS = {
    "Sec0Dia": (0.2700, 0.1620),
    "Sec1Dia": (0.1400, 0.1730),
    "Sec2Dia": (0.0853, 0.1760),
    "Sec3Dia": (0.0785, 0.1880),
    "Sec4Dia": (0.0550, 0.2000),
    # #914: the collar ring is 3.181 wide, too narrow for a dimension line
    # and two arrows inside it, so the collar alone takes the near-side
    # diametric style: one arrow on the top rim from outside, leader up to
    # the text, nothing drawn inside the ring.
    "CollarDia": (0.2088, 0.1760),
}
NEAR_SIDE_DIAMETERS = ("CollarDia",)
# The collar is the 5/8 bar's OD as supplied (user ruling 2026-09-26), so
# its diameter prints as a reference with the stock statement beside it,
# the U41 plate's form.
REFERENCE_DIAMETERS = ("CollarDia",)
# Sheet width of one diameter text with its stacked band, for the layout test.
DIAMETER_TEXT_WIDTH = 0.032
# The collar prints its reference diameter over the stock statement, three
# lines whose widest is "5/8 BAR AS SUPPLIED".  At LENGTH_CHAR_WIDTH a line
# that long is wider than the whole journal land, so hanging right from its
# rim arrow the block ran under the pivot-journal finish and that finish's
# leader crossed it (final877 eye pass).  The build lifts the block above the
# finish symbol, from its measured ink (_clear_collar_callout); the dimension
# line stays on the ring and simply runs longer.
COLLAR_CALLOUT_LINES = (f"(Ø{COLLAR_DIA:.2f})", *COLLAR_STOCK_CALLOUT.split("\n"))
COLLAR_CALLOUT_WIDTH = max(len(line) for line in COLLAR_CALLOUT_LINES) * LENGTH_CHAR_WIDTH
# A measured block narrower than this is a misread (a box around the value
# line alone), not a layout: the proof refuses it rather than clearing it.
COLLAR_CALLOUT_MIN_READ = 0.9 * COLLAR_CALLOUT_WIDTH
DONOR_KEEP = {
    name: (DONOR_CENTER[0], DONOR_CENTER[1] - 0.012 * index)
    for index, name in enumerate(SIDE_DIAMETERS)
}
# Three identical step roots, one modelled fillet, one radius dimension (the
# collar's roots stay sharp, #914).
DIMENSION_CALLOUTS = {
    "ShoulderR": FILLET_CALLOUT,
    "CollarDia": COLLAR_STOCK_CALLOUT,
}
# The pivot-journal finish symbol, above whose ink the collar's text must stand.
PIVOT_FINISH_XY = (0.2400, 0.1800)


class DSection(NamedTuple):
    """One gear land's D-flat section: where the cutting line crosses the
    side view, where the removed section stands, and its own scale."""

    land: int
    label: str
    cut_x: float
    centre: tuple[float, float]
    scale: tuple[int, int]


# The D sections (user ruling 2026-09-28: every gear land carries one flat on
# the shaft's +X).  The side view looks straight at the flats, so their size
# is only readable end-on: each land is cut across mid-land, clear of its
# diameter line, and shown cut-only (nothing beyond the plane prints), each
# enlarged to about 16..19 mm across so the smallest AF, 1.460 on the
# Ø1.588, reads with its band.  The four stand in a row right of the side
# view's baseline stack, under the pictorial and above the title block.  The
# across-flat is the part's own dimension (Sec{i}AF, sketched on the land's
# end plane, parallel to the cut), so it prints its model band and places.
D_SECTIONS = (
    DSection(1, "A", 0.1150, (0.285, 0.100), (2, 1)),
    DSection(2, "B", 0.0876, (0.323, 0.100), (3, 1)),
    DSection(3, "C", 0.0810, (0.361, 0.100), (5, 1)),
    DSection(4, "D", 0.0660, (0.399, 0.100), (10, 1)),
)
# How far a cutting-plane line runs past the land it cuts.
D_SECTION_LINE_OVERRUN = 0.004
# Each across-flat's text, centred over its section.
D_SECTION_KEEP = {
    f"Sec{section.land}AF": (section.centre[0], section.centre[1] + 0.017)
    for section in D_SECTIONS
}
if tuple(section.land for section in D_SECTIONS) != FLAT_LANDS:
    raise AssertionError("every flatted land takes exactly one D section")


@_telemetry.traced("drawing.cylindrical_face_scan")
def _cylindrical_face(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the visible cylindrical face for one shaft diameter."""
    candidates: list[tuple[float, Any]] = []
    for face in visible_view_entities(view, 3, label="gear-shaft side faces"):
        face = _early_bound(face, "IFace2")
        surface = face.GetSurface()
        if surface is None:
            continue
        surface = _early_bound(surface, "ISurface")
        if not surface.IsCylinder():
            continue
        radius_mm = float(surface.CylinderParams[6]) * 1000.0
        candidates.append((radius_mm, face))
    if not candidates:
        raise RuntimeError("side view has no visible cylindrical faces")
    target_radius = diameter_mm / 2.0
    radius_mm, face = min(candidates, key=lambda item: abs(item[0] - target_radius))
    if abs(radius_mm - target_radius) > 0.01:
        raise RuntimeError(
            f"no cylindrical face matches radius {target_radius:.4f} mm; "
            f"nearest is {radius_mm:.4f} mm"
        )
    return face


@_telemetry.traced("drawing.end_face_circle", label_param="label")
def _end_circle(view: Any, *, station_mm: float, diameter_mm: float, label: str) -> Any:
    """The one visible end-face circle (or arc) at ``station_mm`` of ``diameter_mm``.

    The journal's circle also stands at the collar face and the tip land's at
    its own start, so the pick is by station AND diameter.  The tip's end face
    is a D (its flat runs out through the tip), so its edge is the D's arc,
    still a circle curve of the land's radius.  The station is matched on
    |z|: the shaft runs along model Z from the front face, and the sign of
    that axis is the part's, not an assumption made here.
    """
    matches: list[Any] = []
    for raw in visible_view_entities(view, 1, label=f"{label} edges"):
        curve = _early_bound(raw, "IEdge").GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) for value in curve.CircleParams)
        if abs(abs(params[2]) * 1000.0 - station_mm) > 1e-3:
            continue
        if abs(params[6] * 2000.0 - diameter_mm) > 1e-3:
            continue
        matches.append(raw)
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: {len(matches)} end-face circles at z {station_mm:g} "
            f"of Ø{diameter_mm:g}, expected 1"
        )
    return matches[0]


def _add_overall_reference(adapter: Any, side: Any) -> Any:
    """Dimension front stub to tip as a REFERENCE (#917 R5 (a)).

    The tip is a station from the collar face, so the overall is the
    read-only sum of the journal and the tip station: a sheet-derived
    dimension between the two end faces, parenthesized, with the places the
    spec hands over, and its value proved against the part.
    """
    front = _end_circle(
        side, station_mm=0.0, diameter_mm=SECTION_DIAS[0], label="front end face"
    )
    tip = _end_circle(
        side,
        station_mm=SHAFT_LENGTH,
        diameter_mm=SECTION_DIAS[-1],
        label="tip end face",
    )
    display = add_edge_dimension(
        adapter,
        side,
        p0=(0.0, 0.0),
        p1=(0.0, 0.0),
        text_xy=OVERALL_REFERENCE_TEXT_XY,
        label="front-to-tip overall",
        orientation="horizontal",
        entities=(front, tip),
    )
    display = _early_bound(display, "IDisplayDimension")
    measured = abs(
        float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue)
    )
    if abs(measured * 1000.0 - SHAFT_LENGTH) > 1e-4:
        raise RuntimeError(
            f"front-to-tip overall measured {measured * 1000.0:.4f} mm, "
            f"expected {SHAFT_LENGTH:.4f}"
        )
    set_reference_dimension(
        adapter, display.GetAnnotation(), label="front-to-tip overall reference"
    )
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError("front-to-tip overall reference precision did not persist")
    return display


# A centreline runs a short way past the part it marks.
AXIS_OVERRUN = 0.003


def _add_shaft_axis(adapter: Any, view: Any) -> None:
    """Draw the shaft axis end to end as ONE sheet centreline.

    A face-derived centreline (``add_view_centerline``) stops at its own land,
    so the first sheet showed an axis under the journal only (review
    2026-09-23), and ``InsertCenterLine2`` returned nothing for the third land
    (Ø6.35) on the farm (run 772bf5f3), after the first two had succeeded.
    So the axis is sketched on the sheet, as the swing platform's cone axis
    is: through the projected axis the finish leaders already attach to,
    checked against the view outline's mid-height, and AXIS_OVERRUN past each
    end face.
    """
    big_end_x = SIDE_CENTER[0] + SHAFT_LENGTH / 2000.0
    tip_end_x = big_end_x - SHAFT_LENGTH / 1000.0
    axis_y = SIDE_CENTER[1]
    outline = tuple(float(value) for value in view.GetOutline())
    if abs(0.5 * (outline[1] + outline[3]) - axis_y) > 0.0005:
        raise RuntimeError(
            f"side view outline {outline!r} is not centred on the axis y={axis_y}"
        )
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.EditSheet()
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    centerline = manager.CreateCenterLine(
        tip_end_x - AXIS_OVERRUN, axis_y, 0.0, big_end_x + AXIS_OVERRUN, axis_y, 0.0
    )
    if centerline is None:
        raise RuntimeError("failed to sketch the shaft axis centreline")
    # A sheet sketch line prints in the under-defined sketch blue (run
    # f2e72b0f); colour it black, as draw_top_frame's owned centrelines are.
    segment = _early_bound(centerline, "ISketchSegment")
    segment.Color = 0
    if int(segment.Color) != 0:
        raise RuntimeError("shaft axis centreline colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move, never copy, a fitted model dimension and verify its new owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"failed to select model dimension {name}: {selection_name!r}"
        )
    ddoc.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    annotations = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
    ]
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


def _collar_callout_dy(text: Box, finish: Box, finish_leader: Sequence[Segment]) -> float:
    """How far to lift the collar callout so its text clears the pivot-journal
    finish from above: the symbol and every leader run under the text's span.

    Only up: the collar diameter's dimension line stands at its text's left
    edge, so a sideways move drags that line off the ring and its extension
    lines along the rim (mha014-1 moved it 74 mm left, onto land 1's
    Ø9.525 text)."""
    left, right = text[0] - CLEAR_GAP_M, text[2] + CLEAR_GAP_M
    under = [finish[3]] if finish[0] < right and left < finish[2] else []
    under += [
        max(a[1], b[1])
        for a, b in finish_leader
        if min(a[0], b[0]) < right and left < max(a[0], b[0])
    ]
    return max([0.0] + [top + CLEAR_GAP_M + PLACE_SETTLE_M - text[1] for top in under])


def _dimension_text_box(annotation: Any, label: str) -> Box:
    """A dimension's rendered text block: every text item it draws (value,
    stacked band, callout lines), boxed by the layout audit's estimator, since
    no API returns a text's width."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    boxes = []
    for index in range(int(data.GetTextCount())):
        anchor = [float(value) for value in data.GetTextPositionAtIndex(index)]
        reference = int(data.GetTextRefPositionAtIndex(index))
        box = estimate_text_box(
            str(data.GetTextAtIndex(index) or ""),
            anchor=(anchor[0], anchor[1]),
            height=float(data.GetTextHeightAtIndex(index)),
            reference=reference if 0 <= reference <= 5 else 0,
            angle=float(data.GetTextAngleAtIndex(index)),
        )
        if box is not None:
            boxes.append(box)
    if not boxes:
        raise RuntimeError(f"{label} draws no text to measure")
    return (
        min(box.xmin for box in boxes),
        min(box.ymin for box in boxes),
        max(box.xmax for box in boxes),
        max(box.ymax for box in boxes),
    )


def _collar_text(adapter: Any, collar: Any, label: str) -> tuple[Any, Box]:
    """The collar callout's ink and its whole text block, refusing a misread.

    ``callout_ink`` boxes the text from its shoulder; the text positions widen
    that box to every line, so a stock line hung below the shoulder counts.
    """
    ink = callout_ink(adapter, collar, label=label)
    points = dimension_text_points(collar)
    xs = [ink.text[0], ink.text[2], *(x for x, _y in points)]
    ys = [ink.text[1], ink.text[3], *(y for _x, y in points)]
    text = (min(xs), min(ys), max(xs), max(ys))
    if text[2] - text[0] < COLLAR_CALLOUT_MIN_READ:
        raise RuntimeError(
            f"{label} read {text[2] - text[0]:.4f} m wide, under the "
            f"{COLLAR_CALLOUT_MIN_READ:.4f} its widest line needs: a misread"
        )
    return ink, text


@_telemetry.traced("drawing.collar_callout_clear")
def _clear_collar_callout(
    adapter: Any, collar: Any, finish: Any, dimensions: Mapping[str, Any]
) -> None:
    """Lift the collar's stock callout above the pivot-journal finish, then
    prove it from measured ink: its dimension line still on the ring, its
    text clear of the symbol and of every other dimension's text, its leader
    through none of them, no finish leader or dimension line by its text,
    and inside the frame."""
    label = "collar stock callout"
    rebuild_drawing(adapter, label=f"measure {label}")
    finish_annotation = finish.GetAnnotation()
    finish_box = gdt_box(adapter, finish_annotation, label="pivot journal finish")
    finish_leader = leader_segments(finish_annotation)
    _telemetry.info(f"pivot journal finish leader: {finish_leader}")
    _ink, placed = _collar_text(adapter, collar, label)
    dy = _collar_callout_dy(placed, finish_box, finish_leader)
    if dy:
        move_annotation(adapter, collar, 0.0, dy, label=label)
    ink, text = _collar_text(adapter, collar, label)
    if abs(text[0] - placed[0]) > PLACE_SETTLE_M:
        raise RuntimeError(
            f"{label} moved sideways ({placed[0]:.4f} -> {text[0]:.4f}): its "
            "dimension line left the collar ring"
        )
    neighbours = {"pivot journal finish": finish_box}
    lines = {"pivot journal finish": finish_leader}
    for name, dimension in dimensions.items():
        neighbours[name] = _dimension_text_box(dimension, name)
        lines[name] = dimension_segments(dimension)
    require_clear(label, text, neighbours)
    require_leader_clear(ink, neighbours)
    near = [
        name
        for name, segments in lines.items()
        if any(distance_to_box(segment, text) < CLEAR_GAP_M for segment in segments)
    ]
    if near:
        raise RuntimeError(f"{near} lines run by the {label} {text}")
    require_inside(label, text, sheet_region(adapter))
    _telemetry.success(
        f"{label} lifted {dy:.4f} m, clear of the pivot journal finish and "
        f"{len(dimensions)} dimensions"
    )


def _prepare_d_section(adapter: Any, view: Any, section: DSection) -> None:
    """Keep only the D's cut face, at the section's own independent scale."""
    bound = _early_bound(view, "IView")
    bound.UseParentScale = False
    bound.UseSheetScale = 0
    bound.ScaleRatio = double_array([float(section.scale[0]), float(section.scale[1])])
    cut = _early_bound(bound.GetSection(), "IDrSection")
    # R2026x declares SetDisplayOnlySurfaceCut as a void setter; only its
    # dedicated bool getter may be truth-tested.
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label=f"section {section.label} cut face and scale")
    ratio = tuple(float(value) for value in bound.ScaleRatio)
    if (
        bool(bound.UseParentScale)
        or int(bound.UseSheetScale) != 0
        or not math.isclose(ratio[0] / ratio[1], section.scale[0] / section.scale[1])
    ):
        raise RuntimeError(f"section {section.label} scale did not persist: {ratio}")
    if not bool(cut.GetDisplayOnlySurfaceCut()):
        raise RuntimeError(f"section {section.label} kept geometry beyond the cut")
    if bool(cut.GetPartialSection()):
        raise RuntimeError(f"section {section.label} cutting line did not close")


def _add_d_sections(adapter: Any, side: Any) -> None:
    """Cut each flatted land across and print its across-flat in the section.

    ``curate_view_dimensions`` fails the build if a section's across-flat
    does not arrive, so every D on the sheet carries its size."""
    for section in D_SECTIONS:
        reach = SECTION_DIAS[section.land] / 2000.0 + D_SECTION_LINE_OVERRUN
        view = create_section_view(
            adapter,
            side,
            line_start=(section.cut_x, SIDE_CENTER[1] - reach),
            line_end=(section.cut_x, SIDE_CENTER[1] + reach),
            view_xy=section.centre,
            section_label=section.label,
            scale=section.scale,
            label=f"land {section.land} D section",
        )
        _prepare_d_section(adapter, view, section)
        name = f"Sec{section.land}AF"
        curate_view_dimensions(
            adapter,
            view,
            keep={name: D_SECTION_KEEP[name]},
            view_label=f"section {section.label}",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-gear-shaft source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Gear Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone gear shaft; stepped turned steel; gear seats",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=SIDE_SCALE)
    donor = place_view(adapter, str(SOURCE), "*Front", *DONOR_CENTER, scale=SIDE_SCALE)
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, donor):
        set_hidden_lines_removed(adapter, view)

    pivot_face = _cylindrical_face(adapter, side, JOURNAL_DIA)
    tip_face = _cylindrical_face(adapter, side, SECTION_DIAS[-1])
    _add_shaft_axis(adapter, side)

    # The donor is curated FIRST so the diameters cannot be claimed (and then
    # deleted) by a view that cannot show them.
    donor_annotations = curate_view_dimensions(
        adapter,
        donor,
        keep=DONOR_KEEP,
        view_label="diameter donor",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = list(side_annotations)
    collar = None
    for annotation in donor_annotations:
        name = dimension_name(adapter, annotation)
        moved = _move_dimension(
            adapter, annotation, side, SIDE_DIAMETERS[name], source_view=donor
        )
        if name == "CollarDia":
            collar = moved
        if name in NEAR_SIDE_DIAMETERS:
            set_near_side_diameter(moved, f"{name} near-side diameter")
        if name in REFERENCE_DIAMETERS:
            set_reference_dimension(
                adapter, moved, label=f"{name} stock reference", diameter=True
            )
        annotations.append(moved)
    # Every diameter is now native to the view that shows its shoulder; an
    # empty end view carries no manufacturing information.
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter donor view")
    if collar is None:
        raise RuntimeError("the donor view gave no CollarDia dimension")
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _add_d_sections(adapter, side)
    overall = _add_overall_reference(adapter, side)
    # Every other dimension on the side view, which the collar callout's
    # proof measures it against.
    collar_neighbours = {
        dimension_name(adapter, annotation): annotation
        for annotation in annotations
        if annotation is not collar
    }
    collar_neighbours["front-to-tip overall"] = overall.GetAnnotation()
    if len(collar_neighbours) != len(annotations):
        raise RuntimeError(
            f"side view dimensions {sorted(collar_neighbours)} do not name "
            f"the {len(annotations) - 1} beside the collar uniquely"
        )

    # Leader anchors for the two lands that RUN (sheet metres).  The tip
    # symbol stands above the tip with its glyph LEFT of the Ø1.588 dimension
    # line and its text ABOVE the Ø1.588 text, well inside the left border
    # (x 0.012; a glyph at 0.016 poked through it, codex c4720c62); the
    # leader drops onto the tip's top flank inside the first 2 mm of the land.
    # No length extension line runs up there (they all hang from the bottom
    # flank) and no diameter line stands left of the Ø1.588 one.
    big_end_x = SIDE_CENTER[0] + SHAFT_LENGTH / 2000.0
    pivot_top = (big_end_x - 0.020, SIDE_CENTER[1] + SECTION_DIAS[0] / 2000.0)
    tip_top = (
        big_end_x - SHAFT_LENGTH / 1000.0 + 0.002,
        SIDE_CENTER[1] + SECTION_DIAS[-1] / 2000.0,
    )
    pivot_finish = add_surface_finish(
        adapter,
        side,
        symbol_xy=PIVOT_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_journal"),
        label="pivot journal finish",
        char_height=0.0025,
        entity_type="FACE",
        entity=pivot_face,
        leader_attach_xy=pivot_top,
    )
    add_surface_finish(
        adapter,
        side,
        symbol_xy=(0.0240, 0.1960),
        control=surface_finish_by_key(SURFACE_FINISHES, "tip_land"),
        label="tip land finish",
        char_height=0.0025,
        entity_type="FACE",
        entity=tip_face,
        leader_attach_xy=tip_top,
    )
    _clear_collar_callout(adapter, collar, pivot_finish, collar_neighbours)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Gear Shaft Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
