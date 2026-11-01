r"""Create the curated manufacturing drawing for the crank pinion (16T).

Recreated under ``cad/docs/drawing-guidelines.md``. The sheet has an end
view, longitudinal section and isometric of a toothed disc with a hub boss.
Every turned diameter sits beside its axial extent on the longitudinal
section: tooth-tip blank, turned north band, reamed bore and boss, with
shoulder length, face width and overall length from the toothed south face.
The retention pin's reference diameter, its station from the boss's north
face and the normal-pitch gear-data block carry the requirements geometry
cannot convey.

No datums, no feature control frames, no roughness symbol: a custom pinion
pinned to its crankshaft is not on the GD&T allowlist, and its pinned bore
neither runs, slides nor locates (drawing-guidelines.md rule 5 (avoid
excessive GD&T) and rule 6 (roughness symbols only where a surface runs,
slides or locates)). The bore's native limits and feature callout jointly
identify its mating crankshaft and required diametral clearance. The decimal
places are the PART's (``crank_pinion_spec.DRAWING_PRECISION``, applied
natively by ``build_crank_pinion``); this script only reads them back off the
sheet.

Drawn 3:1: the longitudinal section and its diameter/length dimensions
clear the end view and isometric at this common sheet scale. The sheet
prints decimal inch (the part's ``drawing_unit: in``).
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any, Sequence

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimensions,
)
from _drawing_layout_collect import check_drawing_layout
from _drawing_leader_notes import add_leader_note
from _drawing_leaders import (
    assert_leaders_clear,
    leader_segments,
    section_line_segments,
)
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_crank_pinion_spec import (
    BORE_DIA,
    BORE_FIT_CALLOUT,
    BORE_PROCESS_CALLOUT,
    BOSS_DIA,
    CONE_GEAR_NUMBER,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    MESH_GEAR_NUMBER,
    OUTSIDE_DIA,
    OVERALL_LENGTH,
    PIN_HOLE_PROCESS,
    SHOULDER_LENGTH,
    SHOULDER_RADIUS,
    SHOULDER_RADIUS_TOL_TYPE,
    TURNED_DIA_FITUP_CALLOUT,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_pinion"]
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
RIGHT_CENTER = (0.210, 0.150)
# Leave the current full-depth blank's isometric clear of the boss-diameter
# text and the border. The native bounding-box guard remains authoritative.
ISO_CENTER = (0.363, 0.150)

# Half the printed tooth-tip circle, in sheet metres: the face-view silhouette
# radius and the section's half-height, which every dimension is placed clear
# of; and half the printed boss, the section's height past the teeth.
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0
HALF_BOSS = BOSS_DIA * VIEW_SCALE[0] / 2000.0


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
# (drawing-guidelines.md rule 11 (turned parts read like the lathe)); ``BossProfile`` supplies the tooth-tip and bore as construction-only
# native model dimensions so they import without sheet-authored numbers.
FRONT_KEEP: dict[str, tuple[float, float]] = {}
# Longitudinal section. Above the view the three diameters stand on the
# toothed face's side, stepped so no dimension line runs through another's
# text: the bore lowest and the tip diameter next, both outside the faced
# end with their text to the left, and the turned band's highest, its line
# rising inside the band past both. Each diameter's reason rides its own
# callout (machinist review r1 of #1652). The lengths stand on the LOWER
# outline's witnesses, baseline-stacked below the view from the toothed
# south face, shortest innermost (drawing-guidelines.md rule 11 (turned parts
# read like the lathe): one origin per view, baseline not chained); the
# banded two carry their stack callouts, so their text stands outside their
# spans, where the callout lines clear every extension line: the shoulder's
# left of the faced end, below the end view's lower A, the face width's right
# of the boss end, so neither block's lines run through the other's limits
# (r2: stacked on one side, the 8.5 line struck the 11.6's "0.0" and the A
# touched the 8.5's callout). The pin's station reads from the boss's north
# face on the first row. The boss
# diameter reads on a vertical dimension line beyond the boss end, its text
# on the axis between the extension lines: at +0.020 it sat on the upper
# extension line (machinist review of 4d4e038e3), which
# ``_boss_dia_text_crossings`` now rejects on the sheet. The pin hole's
# reference diameter leads up and right through the boss's top wall to its
# callout, clear of the boss diameter's extension lines and right of the
# shoulder radius's callout.
_SIDE_BOTTOM = RIGHT_CENTER[1] - HALF_OD
_SIDE_TOP = RIGHT_CENTER[1] + HALF_OD
BOSS_DIA_TEXT_X = _side_x(OVERALL_LENGTH) + 0.049
# Outside the faced end: centred clear of the end view's A arrow, with the
# widest stack callout still left of the faced end's extension line.
_LENGTH_TEXT_X = _side_x(0.0) - 0.0295
# Its mirror right of the boss end's extension line (the overall length's
# and pin station's), the last line the block's dimension line crosses (r3:
# placed between the shoulder and the boss end, that line struck the text).
_FACE_WIDTH_TEXT_X = _side_x(OVERALL_LENGTH) + 0.030
# The turned diameter's and pin hole's callouts share the top row; the
# turned diameter's block grows left from its leader, so it rises clear of
# the gear data's long rows.
_TOP_ROW_Y = _SIDE_TOP + 0.065
# The tooth-face shoulder's R.016 MAX (machinist review of 88d48ad2a7b4, rules
# 11 and 16), laid out like draw_mg_output_fixture's shoulder radius: the
# arc's centre is up-right of the upper corner, the leader rises from the arc
# nearly plumb, 3 mm right of that centre, to an elbow in the open air over
# the turned band.  The limit is tighter than the title block's R.040 inside
# corners because the MHA-DT-07 64T's tooth tips run over the corner at the
# drive train's worst axial pose (dt_crank_pinion_spec.SHOULDER_RADIUS), so
# its callout names that mate (machinist review of 2056e3344, rule 4): a
# three-row block, R.016 MAX / MHA-DT-07 / TIP CLR, whose widest row (the part
# number, 24.28 mm on that sheet) centres SHOULDER_RADIUS_RUN_IN right of the
# elbow and whose middle stands RADIUS_SHOULDER_DROP, half the block's
# 5.56 mm rows, over its shoulder.  The elbow stands 26 mm over the tooth
# tips, so the wider block's shoulder still ends 3 mm left of the pin hole's
# line, which the inch boss's shorter pin-to-end span steepens (#290).  The leader crosses only the turned diameter's upper extension line;
# the turned diameter's line stands 9 mm left of the elbow.
SHOULDER_ARC_CENTRE = (
    _side_x(FACE_WIDTH + SHOULDER_RADIUS),
    RIGHT_CENTER[1] + HALF_BOSS + SHOULDER_RADIUS * VIEW_SCALE[0] / 1000.0,
)
SHOULDER_RADIUS_ELBOW = (SHOULDER_ARC_CENTRE[0] + 0.003, _SIDE_TOP + 0.026)
SHOULDER_RADIUS_CALLOUT = "\n".join((MESH_GEAR_NUMBER, "TIP CLR"))
SHOULDER_RADIUS_ROWS = 3
SHOULDER_RADIUS_TEXT_HALF_WIDTH = 0.02428 / 2.0
SHOULDER_RADIUS_RUN_IN = SHOULDER_RADIUS_TEXT_HALF_WIDTH + 0.0035
SHOULDER_RADIUS_OVERRUN = 0.00174
RADIUS_SHOULDER_DROP = SHOULDER_RADIUS_ROWS * 0.0027781
# The pin hole's reference diameter runs from the hole's centre to the left
# end of its callout's underline, 55.4 mm left of the keep (88d48ad2a7b4
# audit: keep x 0.275, line to x 0.2196 at y 0.2322).
PIN_HOLE_LINE_RUN_IN = 0.0554
RIGHT_KEEP = {
    "BoreDia": (_side_x(0.0) - 0.0095, _SIDE_TOP + 0.012),
    "OutsideDia": (_side_x(0.0) - 0.003, _SIDE_TOP + 0.027),
    "TurnedDia": (_side_x(SHOULDER_LENGTH + 1.5), _TOP_ROW_Y),
    "BossDia": (BOSS_DIA_TEXT_X, RIGHT_CENTER[1]),
    "PinHoleDia": (0.322, _TOP_ROW_Y),
    "ShoulderLength": (_LENGTH_TEXT_X, _SIDE_BOTTOM - 0.019),
    # The banded text is wider than the hole-to-end span: it stands outside,
    # right of the end face's extension line, so neither line strikes it.
    "PinFromBossEnd": (_side_x(OVERALL_LENGTH) + 0.016, _SIDE_BOTTOM - 0.006),
    "FaceWidth": (_FACE_WIDTH_TEXT_X, _SIDE_BOTTOM - 0.026),
    "OverallLength": (RIGHT_CENTER[0], _SIDE_BOTTOM - 0.043),
    "ShoulderRadius": (
        SHOULDER_RADIUS_ELBOW[0] + SHOULDER_RADIUS_RUN_IN,
        SHOULDER_RADIUS_ELBOW[1] + RADIUS_SHOULDER_DROP,
    ),
}
# The section caption sits under the section, between the overall length's
# extension lines and below its text, above the title block.
SECTION_CAPTION_XY = (0.205, 0.074)
DIMENSION_TEXT_LINE_GAP = 0.0005
# The boss diameter's text is centred on its dimension line; it read 13.1 mm
# wide on the f0c105531 render. Its right edge plus a clearance bounds where
# the isometric's outline may begin.
BOSS_DIA_TEXT_HALF_WIDTH = 0.0075
ISO_TEXT_CLEARANCE = 0.003

# The stack each banded length sets: its short limit keeps full tips in the
# 64T mesh, its long one the T120 clearance (build_dt_drive_train_assembly
# proves both at these bands).
_LENGTH_STACK_CALLOUT = "\n".join(
    (f"{MESH_GEAR_NUMBER} MESH,", f"{CONE_GEAR_NUMBER} T120 CLR")
)
DIMENSION_CALLOUTS = {
    # The native value/limits define the bore; this short feature callout adds
    # the process and extent without tangling its native diameter leaders.
    "BoreDia": BORE_PROCESS_CALLOUT,
    # The tip diameter's band is the 64T mesh's tip-to-root air.
    "OutsideDia": f"{MESH_GEAR_NUMBER} MESH",
    "TurnedDia": TURNED_DIA_FITUP_CALLOUT,
    "ShoulderLength": _LENGTH_STACK_CALLOUT,
    "FaceWidth": _LENGTH_STACK_CALLOUT,
    # Reamed to the pin, so the size is a reference; the words carry the
    # operation, the mate, the pin, the fit's acceptance and flush.
    "PinHoleDia": PIN_HOLE_PROCESS,
    # The shoulder's R MAX is tighter than the title block's inside corners
    # for the 64T's tip clearance over the corner.
    "ShoulderRadius": SHOULDER_RADIUS_CALLOUT,
}
REFERENCE_DIMENSIONS = ("PinHoleDia",)


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


def _dress_shoulder_radius(adapter: Any, annotations: Sequence[Any]) -> None:
    """Prove the section's imported ShoulderRadius prints the part's R MAX
    with its mate callout, and stop its leader at the corner arc.

    Read back: radial (not a diameter), measuring SHOULDER_RADIUS, the native
    swTolMAX the part set, the callout under it. ``ArcExtensionLineOrOppositeSide``
    False keeps the leader from running on through the arc centre into the boss
    (draw_pn_pen_rod._dress_shoulder_radius, draw_mg_output_fixture).
    """
    found = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == "ShoulderRadius"
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one ShoulderRadius on the longitudinal section, found {len(found)}"
        )
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported shoulder radius is not radial")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != SHOULDER_RADIUS_TOL_TYPE:
        raise RuntimeError(
            f"ShoulderRadius lost its native MAX type: {int(tolerance.Type)}"
        )
    if not math.isclose(
        float(dimension.SystemValue), SHOULDER_RADIUS / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError("ShoulderRadius does not measure the shoulder radius")
    callout = str(display.GetText(4) or "")  # swDimensionTextCalloutBelow
    if callout != SHOULDER_RADIUS_CALLOUT:
        raise RuntimeError(f"ShoulderRadius callout did not persist: {callout!r}")
    display.ArcExtensionLineOrOppositeSide = False
    if display.ArcExtensionLineOrOppositeSide is not False:
        raise RuntimeError("ShoulderRadius leader still runs to the opposite side")
    _telemetry.info(
        f"shoulder radius: text {display.GetText(1)!r}, MAX type, callout {callout!r}"
    )


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

SHEET_INNER_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
_BORE_SHEET_RADIUS = BORE_DIA * VIEW_SCALE[0] / 2000.0
_BORE_GAP_ANGLE_RAD = math.radians(168.75)
BORE_FIT_NOTE = (0.016, 0.174)
BORE_FIT_ATTACH = (
    FRONT_CENTER[0] + _BORE_SHEET_RADIUS * math.cos(_BORE_GAP_ANGLE_RAD),
    FRONT_CENTER[1] + _BORE_SHEET_RADIUS * math.sin(_BORE_GAP_ANGLE_RAD),
)
# Where each stroke must END, from the bore centre (sheet metres): the bore
# leader on the rim; the cutting line at its ends past the tooth tips. A
# reading outside the band means the strokes are not sheet metres.
BORE_LANDING = (0.5 * _BORE_SHEET_RADIUS, 1.5 * _BORE_SHEET_RADIUS)
SECTION_LINE_LANDING = (0.0, HALF_OD + 0.010)
# Below the length stack, clear of its stack callouts and the title block.
MANUFACTURING_NOTES_XY = (0.016, 0.076)


def _bore_leader_clears_section_line(adapter: Any, front: Any, bore_fit: Any) -> None:
    """Fail when the bore leader crosses or runs along the A-A cutting line."""
    rebuild_drawing(adapter, label="bore leader vs section line")
    assert_leaders_clear(
        {
            "BoreFit": leader_segments(_early_bound(bore_fit, "INote").GetAnnotation()),
            "SectionLine": section_line_segments(adapter, front),
        },
        centre=FRONT_CENTER,
        keep_out={},
        lands_within={
            "BoreFit": BORE_LANDING,
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
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
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
    _position_section_caption(adapter, right, SECTION_CAPTION_XY)
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
    # The hole is reamed to fit the pin, so its modeled size reads as a
    # reference nominal; the callout under it carries what governs.
    set_reference_dimensions(adapter, right_annotations, REFERENCE_DIMENSIONS)
    assert_imported_precision(
        adapter, front_annotations + right_annotations, DRAWING_PRECISION_BY_NAME
    )
    _boss_dia_text_crossings(adapter, right_annotations)
    _dress_shoulder_radius(adapter, right_annotations)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to pinion bore")
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin cross-hole")
    # The longitudinal section is the turned part's length view: its explicit
    # sketch centerline says which pair of edges is the faced ends (drawing-guidelines.md rule 11 (turned parts read like the lathe)),
    # while the cut exposes the bore so its native diameter never lands on
    # hidden lines.
    _create_section_axis_centerline(
        adapter,
        right,
        label="crank pinion axis",
    )
    # Put the fit note immediately left of the end view and send its short
    # leader radially through the upper-left tooth gap to the visible bore.
    # The native section-view diameter remains beside its axial extent (drawing-guidelines.md rule 11 (turned parts read like the lathe)).
    bore_fit = add_leader_note(
        adapter,
        BORE_FIT_CALLOUT,
        text_xy=BORE_FIT_NOTE,
        attach_xy=BORE_FIT_ATTACH,
        label="crank pinion bore fit",
        view=front,
        height=0.0022,
    )
    _bore_leader_clears_section_line(adapter, front, bore_fit)

    add_property_linked_note(adapter, "Gear Data", 0.016, 0.258, char_height=0.0025)
    add_property_linked_note(
        adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_XY, char_height=0.0025
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
