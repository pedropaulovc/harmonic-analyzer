r"""Create the cone-gear-shaft manufacturing drawing under the simplicity policy.

The turned shaft is shown horizontally at 1:1 with baseline lengths from the
collar's thrust face below it and every diameter above it on that same side
view, each dimension line inside the land it measures (the 1.7 mm collar
instead takes one near-side arrow on its rim).  The two short lands
ahead of the tip are 6.9 mm long, so the three tip-end diameter texts climb
in steps: the tip's line rises highest and each text hangs to the RIGHT of
its line above every line it spans.  A standard isometric supplies pictorial
clarity, and the note names the gear seats the lands are fitted to and the
tailstock support the tip land needs (U40).  Source geometry and
native model fits stay authoritative: the sheet types no tolerance and no
precision.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_gear_shaft.py cone-gear-shaft
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
    visible_view_entities,
)
from _drawing_leaders import set_near_side_diameter
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cone_gear_shaft_spec import (
    COLLAR_STOCK_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_REFERENCE_PRECISION,
    FILLET_CALLOUT,
    JOURNAL_DIA,
    SECTION_DIAS,
    SHAFT_LENGTH,
    SURFACE_FINISHES,
)
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
# y < ~0.066).  The 200.89 mm shaft at 1:1 spans 0.0503..0.2512, leaving the
# right third for the pictorial; the group sits just below mid-height so
# the baseline stack below and the diameters above share the field with the
# note block in the lower left (review 2026-09-23: at 0.170 rows A-B stood
# empty but for the note).  The view is placed by its large end: every
# dimension below is laid out from that datum face, so a change at the tip
# (E1 shortened it 2.9 mm) moves only the tip.
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
# per dimension, the shortest nearest the part: the collar web, the T120
# solder station, the three gear-seat shoulders, the T006 station with its
# 20X EQ SP, then the tip (#917 R5 (a)).  The journal runs the other way from
# the same origin on the first tier, and the front-to-tip overall, a
# reference, hangs lowest, above the title block.  A station's text is
# centred in its span when it fits there with STATION_TEXT_CLEARANCE to spare;
# the web's 1.68 and the T120's 10.78 spans are narrower than their texts, so
# both texts stand stacked LEFT of the T120 extension line (the 916a render
# had the datum line strike "10.781" and the web text touch the collar's
# witness line).  The one radius rides above the 3/8-to-1/4 in step it
# attaches to (the fillet's first edge), right of the Ø6.350 line.
SIDE_KEEP = {
    "CollarWidth": (0.1895, 0.1355),
    "Sec0End": (0.2311, 0.1355),
    "T120Station": (0.1895, 0.1275),
    "Sec1End": (0.1492, 0.1195),
    "Sec2End": (0.1457, 0.1115),
    "Sec3End": (0.1423, 0.1035),
    "T006Station": (0.1388, 0.0955),
    "Sec4End": (0.1307, 0.0875),
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
# land it measures (the big end is at sheet x 0.2526; since U40 land 1 spans
# 0.0888..0.2096, land 2 0.0819..0.0888, land 3 0.0750..0.0819, land 4
# 0.0503..0.0750); Ø12.231 stands just off the faced end.  Lands 2 and 3 are
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
    "Sec4Dia": (0.0520, 0.2000),
    # #914: the collar ring is 1.681 wide, too narrow for a dimension line
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
# The collar's reference diameter, "(Ø15.88)": eight characters on one line.
COLLAR_DIA_TEXT_WIDTH = 0.019
DONOR_KEEP = {
    name: (DONOR_CENTER[0], DONOR_CENTER[1] - 0.012 * index)
    for index, name in enumerate(SIDE_DIAMETERS)
}
# Three identical gear-seat shoulder roots, one modelled fillet, one radius
# dimension (the collar's roots stay sharp, #914).
DIMENSION_CALLOUTS = {
    "ShoulderR": FILLET_CALLOUT,
    "T006Station": "20X EQ SP",
    "CollarDia": COLLAR_STOCK_CALLOUT,
}
# The pivot-journal finish symbol, left of which the collar diameter's text
# must end.
PIVOT_FINISH_XY = (0.2400, 0.1800)


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
    """The one visible end-face circle at ``station_mm`` of ``diameter_mm``.

    The journal's circle also stands at the collar face and the tip land's at
    its own start, so the pick is by station AND diameter.  The station is
    matched on |z|: the shaft runs along model Z from the front face, and the
    sign of that axis is the part's, not an assumption made here.
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
        adapter, donor, keep=DONOR_KEEP, view_label="diameter donor"
    )
    # The part saves its SolderStations witness sketch hidden, so the side
    # view, which owns the two station dimensions, takes the opt-in import
    # that shows it in this view only; the pictorial shows the part as saved.
    side_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = list(side_annotations)
    for annotation in donor_annotations:
        name = dimension_name(adapter, annotation)
        moved = _move_dimension(
            adapter, annotation, side, SIDE_DIAMETERS[name], source_view=donor
        )
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
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _add_overall_reference(adapter, side)

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
    add_surface_finish(
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
        control=surface_finish_by_key(SURFACE_FINISHES, "tip_journal"),
        label="tip journal finish",
        char_height=0.0025,
        entity_type="FACE",
        entity=tip_face,
        leader_attach_xy=tip_top,
    )
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
