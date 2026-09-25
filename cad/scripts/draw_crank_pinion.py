r"""Create the curated manufacturing drawing for the crank pinion (16T).

Recreated under ``cad/docs/drawing-simplicity-policy.md``. The sheet has an end
view, longitudinal section and isometric of a toothed disc with a hub boss and
six native model dimensions. Every turned diameter sits beside its axial
extent on the longitudinal section: tooth-tip blank, reamed bore and boss, with
face width, overall length and the boss end break. The retention pin's
matched-fit hole callout and the gear-data block carry the process facts that
geometry cannot.

No datums, no feature control frames, one roughness symbol (the bore): a
removable stock pinion pinned to its crankshaft is not on the GD&T allowlist
(rules 3-5). The bore's native limits and feature callout jointly identify its
mating crankshaft and required diametral clearance. The decimal places are the
PART's (``crank_pinion_spec.DRAWING_PRECISION``, applied natively by
``build_crank_pinion``); this script only reads them back off the sheet.

Drawn 3:1 -- W15's boss makes the part 24.9 long: at 4:1 the section's
boss-end dimensions ran into the isometric, and at 5:1 the isometric had
already run off the B sheet's right border.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any, Sequence

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_leader_note,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    check_drawing_layout,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
)
from _drawing_leaders import (
    assert_leaders_clear,
    leader_segments,
    section_line_segments,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from crank_pinion_spec import (
    BORE_DIA,
    BORE_FIT_CALLOUT,
    BORE_PROCESS_CALLOUT,
    BOSS_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    OUTSIDE_DIA,
    OVERALL_LENGTH,
    PIN_DIA,
    PIN_HOLE_PROCESS,
    PIN_STATION,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_pinion"]
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

SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
FRONT_CENTER = (0.110, 0.150)
RIGHT_CENTER = (0.215, 0.150)
# At 0.345 the isometric's outline began under the boss diameter's text
# (eye pass of f0c105531); ``_isometric_clears_boss_dia`` now holds it clear.
# The guard reads the view's bounding box, +-0.0509 about its centre at 3:1
# (w15-301f4bf4e read-back), wider than the drawn silhouette: 0.360 failed it
# by 2.7 mm, and 0.365 clears the text by 2.3 mm and the border by 3.2 mm.
ISO_CENTER = (0.365, 0.150)

# Half the printed tooth-tip circle, in sheet metres: the face-view silhouette
# radius and the section's half-height, which every dimension is placed clear
# of; and half the printed boss, the section's height past the teeth.
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0  # 0.0267
HALF_BOSS = BOSS_DIA * VIEW_SCALE[0] / 2000.0  # 0.0203


def _side_x(z_mm: float) -> float:
    """Sheet x of a model-z station in the longitudinal section.

    SolidWorks centres the derived view on its geometry, and this section lays
    model +Z to the RIGHT: the toothed south face (z = 0) is the left edge and
    the boss end is the right edge.
    """
    return RIGHT_CENTER[0] + (z_mm - OVERALL_LENGTH / 2.0) * VIEW_SCALE[0] / 1000.0

@_telemetry.traced("drawing.planar_centerline", label_param="label")
def _create_section_axis_centerline(
    adapter: Any,
    view: Any,
    *,
    label: str,
) -> Any:
    """Create the retained turning axis in the longitudinal-section sketch."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not drawing.ActivateView(name):
        raise RuntimeError(f"failed to activate section view {name!r} ({label})")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    previous_display = bool(sketch_manager.DisplayWhenAdded)
    sketch_manager.AddToDB = True
    sketch_manager.DisplayWhenAdded = True
    half_length = OVERALL_LENGTH / 2000.0
    try:
        centerline = sketch_manager.CreateCenterLine(
            -half_length - 0.001,
            0.0,
            0.0,
            half_length + 0.001,
            0.0,
            0.0,
        )
    finally:
        sketch_manager.AddToDB = previous_add_to_db
        sketch_manager.DisplayWhenAdded = previous_display
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError(f"failed to create section-axis centerline ({label})")
    return centerline

def _position_section_caption(
    adapter: Any,
    view: Any,
    target: tuple[float, float],
) -> None:
    """Move the native linked section caption clear of the length dimensions."""
    bound_view = _early_bound(view, "IView")
    candidates = []
    for raw_note in bound_view.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if all(token in linked_text for token in ("<VLNAME>", "<VLLABEL>", "<VLSCALEV>")):
            candidates.append((note, linked_text))
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one native linked section caption, found {len(candidates)}"
        )
    note, linked_text = candidates[0]
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*target, 0.0):
        raise RuntimeError("failed to position crank-pinion section caption")
    rebuild_drawing(adapter, label="position crank-pinion section caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], target) > 1e-6:
        raise RuntimeError("crank-pinion section caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError("crank-pinion section caption lost its native fields")



# The end view is pictorial and carries only its center mark. Every turned
# diameter belongs beside the matching axial extent on the longitudinal section
# (rule 7); ``BossProfile`` supplies the tooth-tip and bore as construction-only
# native model dimensions so they import without sheet-authored numbers.
FRONT_KEEP: dict[str, tuple[float, float]] = {}
# Longitudinal section: the tooth-tip diameter sits above its axial span; the
# bore diameter sits just right of the silhouette, still clear of the
# isometric. The two lengths stay baseline-stacked below the view from the
# toothed south face (rule 7: one origin per view, baseline not chained). The
# boss diameter reads on a vertical dimension line beyond the boss end, its
# text on the axis between the extension lines: at +0.020 it sat on the upper
# extension line (machinist review of 4d4e038e3), which
# ``_boss_dia_text_crossings`` now rejects on the sheet.
_SIDE_BOTTOM = RIGHT_CENTER[1] - HALF_OD
BOSS_DIA_TEXT_X = _side_x(OVERALL_LENGTH) + 0.049
RIGHT_KEEP = {
    "OutsideDia": (
        (_side_x(0.0) + _side_x(FACE_WIDTH)) / 2.0,
        RIGHT_CENTER[1] + HALF_OD + 0.012,
    ),
    "BossDia": (BOSS_DIA_TEXT_X, RIGHT_CENTER[1]),
    "BoreDia": (_side_x(OVERALL_LENGTH) + 0.020, RIGHT_CENTER[1]),
    "FaceWidth": ((_side_x(0.0) + _side_x(FACE_WIDTH)) / 2.0, _SIDE_BOTTOM - 0.014),
    "OverallLength": (RIGHT_CENTER[0], _SIDE_BOTTOM - 0.026),
}
DIMENSION_TEXT_LINE_GAP = 0.0005
# The boss diameter's text is centred on its dimension line; it read 13.1 mm
# wide on the f0c105531 render. Its right edge plus a clearance bounds where
# the isometric's outline may begin.
BOSS_DIA_TEXT_HALF_WIDTH = 0.0075
ISO_TEXT_CLEARANCE = 0.003

DIMENSION_CALLOUTS = {
    # The native value/limits define the bore; this short feature callout adds
    # the process and extent without tangling its native diameter leaders.
    "BoreDia": BORE_PROCESS_CALLOUT,
}


Point = tuple[float, float]


def _text_line_crossings(
    texts: Sequence[tuple[float, float, float]],
    lines: Sequence[tuple[Point, Point]],
    gap: float,
) -> list[tuple[Point, Point]]:
    """The horizontal ink lines that run through a dimension's text.

    ``texts`` are the display data's (x, y, height) text origins. The origin
    may be the text's base or its middle, so a text claims y - height ..
    y + height, widened by ``gap``; a horizontal line crosses it when its y is
    in that band and its x-span reaches the origin.
    """
    crossings = []
    for (x0, y0), (x1, y1) in lines:
        if abs(y1 - y0) > 1e-6:
            continue
        for x, y, height in texts:
            if abs(y0 - y) <= height + gap and min(x0, x1) <= x <= max(x0, x1):
                crossings.append(((x0, y0), (x1, y1)))
                break
    return crossings


def _boss_dia_text_crossings(adapter: Any, annotations: Sequence[Any]) -> None:
    """Fail when the boss diameter's text sits on one of its own lines."""
    for annotation in annotations:
        annotation = _early_bound(annotation, "IAnnotation")
        if dimension_name(adapter, annotation) != "BossDia":
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        data = _early_bound(display.GetDisplayData(), "IDisplayData")
        lines = []
        for index in range(int(data.GetLineCount())):
            line = tuple(float(value) for value in data.GetLineAtIndex2(index))
            if len(line) < 10:
                raise RuntimeError("BossDia: incomplete native dimension line")
            lines.append(((line[4], line[5]), (line[7], line[8])))
        texts = [
            (
                *(float(v) for v in tuple(data.GetTextPositionAtIndex(index))[:2]),
                float(data.GetTextHeightAtIndex(index)),
            )
            for index in range(int(data.GetTextCount()))
        ]
        crossings = _text_line_crossings(texts, lines, DIMENSION_TEXT_LINE_GAP)
        _telemetry.event(
            "drawing.boss_dia_text", texts=str(texts), lines=len(lines), crossings=len(crossings)
        )
        if not texts or crossings:
            raise RuntimeError(f"BossDia text {texts} sits on its lines {crossings}")
        return
    raise RuntimeError("BossDia never reached the longitudinal section")


def _isometric_clears_boss_dia(iso: Any) -> None:
    """Fail when the isometric starts under the boss diameter's text or leaves the border."""
    outline = tuple(float(value) for value in iso.GetOutline())
    if len(outline) != 4:
        raise RuntimeError(f"isometric has invalid bounds {outline}")
    _telemetry.event("drawing.isometric_outline", outline=str(outline))
    text_right = BOSS_DIA_TEXT_X + BOSS_DIA_TEXT_HALF_WIDTH + ISO_TEXT_CLEARANCE
    if outline[0] < text_right:
        raise RuntimeError(
            f"isometric outline {outline} starts left of the boss diameter text's {text_right:.4f}"
        )
    if outline[2] > SHEET_INNER_BORDER[2]:
        raise RuntimeError(
            f"isometric outline {outline} left the inner border {SHEET_INNER_BORDER}"
        )

# The retention-pin cross-hole is cut in section at the boss mid-length. Keep
# its matched-fit callout above-right of the section so its leader leaves the
# text cleanly, crosses only the boss, and lands at the upper cut edge.
PIN_HOLE_EDGE = (
    _side_x(PIN_STATION),
    RIGHT_CENTER[1] + PIN_DIA * VIEW_SCALE[0] / 2000.0,
)
PIN_HOLE_CALLOUT = (0.260, RIGHT_CENTER[1] + HALF_OD + 0.056)
# The shared matched-fit note (crank_pinion_spec.pin_hole_note): match drill
# with the shaft at the boss mid-length, ream to fit the named pin (the fit to
# the actual pin governs the hole, not a drill size), the fit's acceptance and
# flush both sides.
PIN_HOLE_NOTE = PIN_HOLE_PROCESS
# 2.5 mm text, anchored upper-left; the read-back extent, leader included,
# must stay inside the B sheet's inner border.
PIN_HOLE_NOTE_HEIGHT = 0.0025
SHEET_INNER_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
_BORE_SHEET_RADIUS = BORE_DIA * VIEW_SCALE[0] / 2000.0
_BORE_GAP_ANGLE_RAD = math.radians(168.75)
BORE_FIT_NOTE = (0.016, 0.174)
BORE_FIT_ATTACH = (
    FRONT_CENTER[0] + _BORE_SHEET_RADIUS * math.cos(_BORE_GAP_ANGLE_RAD),
    FRONT_CENTER[1] + _BORE_SHEET_RADIUS * math.sin(_BORE_GAP_ANGLE_RAD),
)
# The bore finish lands at -45 degrees, lower right: dropped straight to the
# bore's bottom, its leader started on the A-A cutting-plane line (eye pass of
# w15-3d3a9d762). The symbol stands right of the end view, clear of the teeth
# and of the lower A arrow; ``_bore_leaders_clear_section_line`` reads the
# cutting line back and fails on any crossing or overlap with it.
FINISH_ATTACH = (
    FRONT_CENTER[0] + _BORE_SHEET_RADIUS * math.cos(math.radians(-45.0)),
    FRONT_CENTER[1] + _BORE_SHEET_RADIUS * math.sin(math.radians(-45.0)),
)
FINISH_SYMBOL = (FRONT_CENTER[0] + HALF_OD + 0.010, FRONT_CENTER[1] - 0.015)
# Where each stroke must END, from the bore centre (sheet metres): both bore
# leaders on the rim; the cutting line at its ends past the tooth tips. A
# reading outside the band means the strokes are not sheet metres.
BORE_LANDING = (0.5 * _BORE_SHEET_RADIUS, 1.5 * _BORE_SHEET_RADIUS)
SECTION_LINE_LANDING = (0.0, HALF_OD + 0.010)


def _bore_leaders_clear_section_line(
    adapter: Any, front: Any, bore_fit: Any, finish: Any
) -> None:
    """Fail when either bore leader crosses or runs along the A-A cutting line."""
    rebuild_drawing(adapter, label="bore leaders vs section line")
    assert_leaders_clear(
        {
            "BoreFit": leader_segments(_early_bound(bore_fit, "INote").GetAnnotation()),
            "BoreFinish": leader_segments(finish.GetAnnotation()),
            "SectionLine": section_line_segments(front),
        },
        centre=FRONT_CENTER,
        keep_out={},
        lands_within={
            "BoreFit": BORE_LANDING,
            "BoreFinish": BORE_LANDING,
            "SectionLine": SECTION_LINE_LANDING,
        },
        label="crank pinion end view",
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-pinion source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
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
            0: "Crank Pinion Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank pinion; steel; 16T spur",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = create_section_view(
        adapter,
        front,
        line_start=(FRONT_CENTER[0], FRONT_CENTER[1] - HALF_OD - 0.005),
        line_end=(FRONT_CENTER[0], FRONT_CENTER[1] + HALF_OD + 0.005),
        view_xy=RIGHT_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="crank pinion longitudinal centre section",
    )
    _position_section_caption(adapter, right, (0.290, 0.085))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)
    _isometric_clears_boss_dia(iso)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="longitudinal section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *right_annotations], DIMENSION_CALLOUTS
    )
    assert_imported_precision(
        adapter, front_annotations + right_annotations, DRAWING_PRECISION_BY_NAME
    )
    _boss_dia_text_crossings(adapter, right_annotations)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to pinion bore")
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin cross-hole")
    # The longitudinal section is the turned part's length view: its explicit
    # sketch centerline says which pair of edges is the faced ends (rule 7),
    # while the cut exposes the bore so its native diameter never lands on
    # hidden lines.
    _create_section_axis_centerline(
        adapter,
        right,
        label="crank pinion axis",
    )
    # The cross-hole is governed by a matched fit, not the model's nominal
    # drill diameter. The pinion's boss guides the drill, so its rim carries
    # the operation, where it runs, the mating part, the pin it is reamed to,
    # the fit's acceptance and the flush condition.
    # A longitudinal section presents the radial through-hole as cut edges, not
    # a selectable model circle, so this view-owned pointer names its cut
    # location without dimensioning that hole.
    pin_note = add_leader_note(
        adapter,
        PIN_HOLE_NOTE,
        text_xy=PIN_HOLE_CALLOUT,
        attach_xy=PIN_HOLE_EDGE,
        label="retention-pin matched cross-hole",
        view=right,
        height=PIN_HOLE_NOTE_HEIGHT,
    )
    adapter.currentModel.GraphicsRedraw2()
    extent = tuple(float(v) for v in (_early_bound(pin_note, "INote").GetExtent() or ()))
    _telemetry.info(f"retention-pin note extent {extent}")
    x0, y0, x1, y1 = SHEET_INNER_BORDER
    if len(extent) < 5 or not (
        x0 <= extent[0] and y0 <= extent[1] and extent[3] <= x1 and extent[4] <= y1
    ):
        raise RuntimeError(
            f"retention-pin note extent {extent} left the inner border {SHEET_INNER_BORDER}"
        )
    # Put the fit note immediately left of the end view and send its short
    # leader radially through the upper-left tooth gap to the visible bore.
    # The native section-view diameter remains beside its axial extent (rule 7).
    bore_fit = add_leader_note(
        adapter,
        BORE_FIT_CALLOUT,
        text_xy=BORE_FIT_NOTE,
        attach_xy=BORE_FIT_ATTACH,
        label="crank pinion bore fit",
        view=front,
        height=0.0022,
    )
    # The fit note and finish symbol use different bore quadrants, so their
    # leaders cannot be mistaken for one another.
    # The bore is the part's one fit surface, and a fit is a function of the
    # peaks as well as the size: REAM names the operation, not the finish it
    # leaves. The roughness is the project's general machined grade, authored
    # on the PART and read back here (policy rule 5's "a surface that has to
    # work" case). A surface symbol's native anchor is its lower-left corner,
    # and its text grows rightward; place it right of the face view, clear of
    # the A-A cutting-plane line.
    finish = add_surface_finish(
        adapter,
        front,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "crank_pinion_bore"),
        label="crank pinion bore finish",
        entity=visible_circle_edge(adapter, front, BORE_DIA),
        leader_attach_xy=FINISH_ATTACH,
        char_height=0.0025,
    )
    _bore_leaders_clear_section_line(adapter, front, bore_fit, finish)

    add_property_linked_note(adapter, "Gear Data", 0.016, 0.258, char_height=0.0025)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, 0.082, char_height=0.0025
    )
    rebuild_drawing(adapter, label="crank pinion layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Pinion Manufacturing Drawing",
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
