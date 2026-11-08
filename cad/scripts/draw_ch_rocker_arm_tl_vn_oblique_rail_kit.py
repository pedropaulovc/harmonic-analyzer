"""Draw the two installed members of one NUIBBYED HGR15 rail kit (MHA-CH-06-TL-VN-83).

Sheet 1 is the configured purchased-part reference: ``[1] RAIL`` as its
isometric only, its header pointing at sheet 2 (at 1:8 its orthographic
views read as a bar and dots, farm run 20261105T035724094Z), ``[2]
CARRIAGE`` in four native views; each member's installed quantity, the kit
as the purchase unit, and the carriage's note (the owner's kit description
and the fit-up play acceptance in MHA-CH-06-TL-00).

Sheet 2 shows nominal REF geometry for the matched rail/bar route. Trim the
actual rail flush with its actual bar and transfer its eight mounting holes.
The first hole's station and the length are model-linked, parenthesised and
untoleranced; the flag under them gives the rest as one REF pattern
(``8X HOLES ON (60.000) PITCH``, rule 10) with its match-transfer mate. The
end wall is the model's ``EndWall`` reference, far end face to far
counterbore edge, its callout ``2X, 2.0 MIN AFTER TRIM``. No supplier pitch
accuracy or transfer-tool accuracy is claimed. Free screw insertion,
retained actual walls and full travel accept the pair (the jig's steps).
FRONT (the hole face) and TOP stand at the sheet's 1:2 and print no
scale; the end profile is VIEW B at 2:1, so its raceway grooves read, named
by a letter arrow on TOP's far end; the isometric at 1:4.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    view_name,
)

import _telemetry
import ch_rocker_arm_tl_vn_oblique_rail_kit_carriage_spec as carriage
import ch_rocker_arm_tl_vn_oblique_rail_kit_rail_spec as rail
from _com import _early_bound
from _drawing_annotation_extent import CLEAR_GAP_M, boxes_clear
from _drawing_common import read_required_properties
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_leader_notes import add_attached_note, add_leader_note
from _drawing_layout_check import LeaderSegment, _segment_crosses_box
from _drawing_leaders import Box, Segment, dimension_segments
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheet_region import sheet_drawable_region
from _drawing_types import DRAWING_TEMPLATES
from _drawing_view_display import set_hidden_lines_removed
from _layout_geometry import estimate_text_box
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import (
    _box,
    _center_marks_without_lines,
    _inside,
    _literal_note,
    _purchased_title_block,
    _rebuild,
)
from _purchased_title_fit import fit_purchased_title_block
from _purchased_variant_drawing import (
    build_purchased_variant_drawing,
    configure_reference_views,
)
from _session import run_build

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_rail_kit"]
PART_STEM = SPEC.artifact_stem
SOURCE = SPEC.source

# --- Sheet 1: the configured purchased-part reference ---------------------------
# The footer's ITEM row: the kit's style designations in plain text.
ITEM = "GENERIC HIWIN-STYLE HGR15 RAIL + HGH15CA CARRIAGE KIT, NUIBBYED"
# Literal, as the source-property census reads it; the guard below ties it
# to the member specs' configurations and item tags.
VARIANTS = (
    ("Rail", "[1] RAIL"),
    ("Carriage", "[2] CARRIAGE"),
)
if VARIANTS != (
    (rail.CONFIGURATION, f"{rail.ITEM_TAG} RAIL"),
    (carriage.CONFIGURATION, f"{carriage.ITEM_TAG} CARRIAGE"),
):
    raise AssertionError("the sheet's member labels drifted from the member specs")
PURCHASE_UNIT = "ONE KIT OF 2 RAILS AND 4 CARRIAGES"
RECEIPT_SHEET_NAME = "RAIL RECEIPT"
SHEET_NAMES = (RECEIPT_SHEET_NAME,)
if SHEET_NAMES.index(RECEIPT_SHEET_NAME) + 2 != rail.RECEIPT_SHEET:
    raise AssertionError("the rail's receipt citations name the wrong sheet")
# Sheet 2 draws the rail's orthographic views; sheet 1 shows its isometric.
ISOMETRIC_ONLY = {rail.CONFIGURATION: rail.RECEIPT_SHEET}
GENERAL_TEXT = (
    f"REFERENCE VIEWS; {rail.ITEM_TAG} RECEIPT CHECK PER SHEET {rail.RECEIPT_SHEET}; "
    f"{carriage.ITEM_TAG} AS SUPPLIED."
)
# Sheet 1's footer note is the carriage's: the rail's prints on its sheet.
FOOTER_NOTES = carriage.DRAWING_NOTES
# The source's document-level member notes (build_..._rail_kit).
NOTE_PROPERTIES = {
    f"{rail.CONFIGURATION} Manufacturing Notes": rail.DRAWING_NOTES,
    f"{carriage.CONFIGURATION} Manufacturing Notes": carriage.DRAWING_NOTES,
}
SOURCE_PROPERTIES = ("Number", "Material Specification", "Finish", *NOTE_PROPERTIES)

# --- Sheet 2: the rail receipt check --------------------------------------------
# ASME B landscape 431.8 x 279.4, all in sheet metres. The border is 12.7 mm
# in; the title block fills x >= 215.9 mm below y = 65.1 mm. The rail's one
# requirement is the EndWall dimension's callout, so this sheet has no footer
# note.
#
# The trimmed rail fits at 1:2, the largest project scale whose
# length fits the drawable width with the profile beside it.
SHEET_SCALE = (1, 2)
# The 15 x 15 profile prints 30 mm square at 2:1 (7.5 mm at the sheet's 1:2,
# where its R1.62 raceway grooves blur).
PROFILE_SCALE = (2, 1)
# The isometric at 1:4: about 80 x 50 mm, upper right.
ISO_SCALE = (1, 4)


def _sheet_mm(scale: tuple[int, int]) -> float:
    """Sheet metres per model mm at ``scale``."""
    return scale[0] / scale[1] / 1000.0


# IView.GetOutline pads the model box by a fixed 5.59 mm a side
# (draw_vn_pen_marker, farm run e31912e0).
_OUTLINE_PAD = 0.00559
_CELL_SLACK = 0.002  # reserved cell beyond the expected outline, each side

# Model-box half-extents on the sheet. FRONT looks down on the hole face
# (length x width), TOP at the flank (length x height), RIGHT along the rail
# at the end profile (width x height). The isometric's box is the r9 sheet's
# 1:4 pictorial of the 440 rail (about 81 x 48 mm) read off its PDF.
_FRONT_HALF = (
    rail.LENGTH / 2.0 * _sheet_mm(SHEET_SCALE),
    rail.WIDTH / 2.0 * _sheet_mm(SHEET_SCALE),
)
_TOP_HALF = (
    rail.LENGTH / 2.0 * _sheet_mm(SHEET_SCALE),
    rail.HEIGHT / 2.0 * _sheet_mm(SHEET_SCALE),
)
_RIGHT_HALF = (
    rail.HEIGHT / 2.0 * _sheet_mm(PROFILE_SCALE),
    rail.WIDTH / 2.0 * _sheet_mm(PROFILE_SCALE),
)
_ISO_HALF = (0.045, 0.028)

# FRONT/TOP leave a left-hand text lane for the two shortest stations.
# Its extra 2 mm border reserve accommodates the measured native text widths.
# Eight station rows, the receipt flag and the FRONT caption stand under it,
# down to the footer, the length row over it; TOP stands over FRONT, in
# projection with it. RIGHT stands level with FRONT, right of its end; the
# isometric fills the upper right, clear of TOP's end and over RIGHT's
# outline.
FRONT_CENTER = (0.172, 0.160)
# TOP's caption reserve starts at Y=190.96 mm. After the native Length
# placement correction, its full callout tops out at 188.50 mm in the
# conservative text fixture (187.0 mm from the translated native bounds).
TOP_CENTER = (FRONT_CENTER[0], 0.211)
RIGHT_CENTER = (0.340, FRONT_CENTER[1])
ISO_CENTER = (0.345, 0.230)
VIEWS = (
    ("*Front", FRONT_CENTER, _FRONT_HALF, SHEET_SCALE),
    ("*Top", TOP_CENTER, _TOP_HALF, SHEET_SCALE),
    ("*Right", RIGHT_CENTER, _RIGHT_HALF, PROFILE_SCALE),
    ("*Isometric", ISO_CENTER, _ISO_HALF, ISO_SCALE),
)


def view_cell(
    center: tuple[float, float], half: tuple[float, float]
) -> tuple[float, float, float, float]:
    """The reserved box a view's native outline must stay inside."""
    reach_x = half[0] + _OUTLINE_PAD + _CELL_SLACK
    reach_y = half[1] + _OUTLINE_PAD + _CELL_SLACK
    return (
        center[0] - reach_x,
        center[1] - reach_y,
        center[0] + reach_x,
        center[1] + reach_y,
    )


# FRONT's receipt dimensions (rule 10, baseline from the -X end face): the
# shortest station in the row nearest the part, each longer one a row
# further out, so no extension line crosses a dimension line or a text.
# Each text's centre stands its row's drop under the rail's centreline,
# between its extension lines, except where ``TEXT_OUTSIDE_START`` moves it.
#
# SolidWorks prints a linear dimension's text over its dimension line, the
# text at the requested point: on run 20261104T222143958Z each station's
# 3.5 mm text centre stood 2.6 mm over its line, its foot 0.85 mm over it.
DIMENSION_TEXT_HEIGHT = 0.0035
TEXT_OVER_LINE = 0.0026
# A text's foot this close over its own line reads as sitting on it; the 435
# value that stood 6.6 mm off its line on that run fails.
TEXT_ON_LINE_MAX = 0.002
# Every text clears every other dimension's lines and texts by CLEAR_GAP_M.
# A row's text tops out TEXT_OVER_LINE plus half a text height over its own
# line, 4.35 mm; a nearer row's extension lines overrun its line by about
# 1.6 mm, over the next row's text where that text spans them (the 75 and
# 135 values span the 15 and 75 stations). The pitch leaves 2.55 mm over
# that, the next row's line 4.15 mm.
STATION_FIRST_DROP = 0.008
STATION_ROW_PITCH = 0.0085
# Native 957501d1 Length ink was X=50.6..187.3, Y=170.4..183.0 mm,
# intersecting its X=62 mm witness. Move its existing text target right
# 20 mm and up 4 mm: ink then clears both witnesses and TOP's caption.
LENGTH_ROW_RISE = 0.020
LENGTH_TEXT_SHIFT = 0.020
# The first station alone locates the pattern; the flag gives the pitch
# (rule 10: one regular pattern counts as one axis, so eight station
# dimensions are not needed).
DRAWN_STATIONS = rail.STATION_DIMENSIONS[:1]
RECEIPT_DIMENSIONS = {
    name: (0.0, x, -(STATION_FIRST_DROP + index * STATION_ROW_PITCH))
    for index, (name, x) in enumerate(
        zip(DRAWN_STATIONS, rail.HOLE_X, strict=False)
    )
}
RECEIPT_DIMENSIONS["Length"] = (0.0, rail.LENGTH, LENGTH_ROW_RISE)
STATION_NOMINALS = dict(zip(DRAWN_STATIONS, rail.HOLE_X, strict=False))
# The end wall (2X) at the FAR end, where its model chord runs, clear of
# Station1's near-end stack: far counterbore edge (its start, the left
# witness) to the far end face. Its value and its callout below stack two
# rows over its line (a callout under a station lifted that value 2.5 mm,
# run 20261104T222143958Z), so its text centre stands that much deeper than
# Station1's: the block's top keeps Station1's air under the rail.
END_WALL_NAME = rail.END_WALL_DIMENSION
END_WALL_DROP = STATION_FIRST_DROP + 0.0025
RECEIPT_DIMENSIONS[END_WALL_NAME] = (
    rail.LENGTH - rail.END_WALL, rail.LENGTH, -END_WALL_DROP
)
RECEIPT_NOMINALS = {
    **STATION_NOMINALS, END_WALL_NAME: rail.END_WALL, "Length": rail.LENGTH,
}
RECEIPT_CALLOUTS_BELOW = {END_WALL_NAME: rail.END_WALL_CALLOUT}
# Neither short span holds its text or its two native arrowheads: each text
# stands outside its span's left witness, its arrows outside. The station's
# 4.982 mm span: 27 mm, half its text + the padded cell's 7.59 mm reach + the
# 2 mm gap. The end wall's 3.107 mm span: 28 mm, half its 22-character
# callout (49.3 mm at the flag's measured 2.243 mm a character, farm run
# 20261108T000844770Z) + 3.5 mm, its text inside the rail's run, right of
# the flag's cell.
TEXT_OUTSIDE_START = {**dict.fromkeys(DRAWN_STATIONS, 0.027), END_WALL_NAME: 0.028}
_DIM_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
RECEIPT_ARROW_SIDES = dict.fromkeys((*DRAWN_STATIONS, END_WALL_NAME), _DIM_ARROWS_OUTSIDE)
_CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow
_TOL_NONE = 0  # swTolType_e.swTolNONE
# Only the drawn dimensions' places: curation deletes the other stations, so
# the readback must not expect them.
FRONT_DIMENSION_PRECISION = {
    name: places
    for places_by_name in rail.DRAWING_PRECISION.values()
    for name, places in places_by_name.items()
    if name in RECEIPT_DIMENSIONS
}
# The flag: the hole pattern's callout, centred under the station (a callout
# on the station stacked that value onto the row over it), its leader to one
# hole's counterbore (rule 7: a match-transfer requirement is the feature's
# callout, leadered; as loose text under the view it failed machinist review,
# farm run 20261108T015328529Z). Its top stands 4 mm under the station's
# line, under its extension lines' overrun; its two lines are the pattern
# and its match-transfer mate.
_LAST_ROW_LINE_DROP = (
    STATION_FIRST_DROP
    + (len(DRAWN_STATIONS) - 1) * STATION_ROW_PITCH
    + TEXT_OVER_LINE
)
RECEIPT_FLAG_XY = (FRONT_CENTER[0], FRONT_CENTER[1] - _LAST_ROW_LINE_DROP - 0.004)
# Its 42-character second line printed 94.2 mm wide, centred on FRONT
# (farm run 20261108T000844770Z): the note's upper-left anchor stands half
# that left of centre. The cell reaches 28 mm left of the text for the
# leader's start, 3.9 mm right of it: the end wall's text stands beyond.
RECEIPT_FLAG_CELL = (
    RECEIPT_FLAG_XY[0] - 0.075,
    RECEIPT_FLAG_XY[1] - 0.011,
    RECEIPT_FLAG_XY[0] + 0.051,
    RECEIPT_FLAG_XY[1] + 0.001,
)
RECEIPT_FLAG_ANCHOR = (RECEIPT_FLAG_XY[0] - 0.047, RECEIPT_FLAG_XY[1])
# The leader lands on the second hole's counterbore rim, down-right at 45°:
# that hole stands left of the text's left edge, so the leader rises
# up-left from the text's left side without crossing it (on the fourth
# hole, over the text, it ran through the "8", farm run
# 20261108T031012373Z), and right of the station's lines at the near end.
RECEIPT_FLAG_HOLE = 1
_FLAG_RIM = rail.CBORE_DIA / 2.0 * _sheet_mm(SHEET_SCALE) / math.sqrt(2.0)
RECEIPT_FLAG_LANDING = (
    FRONT_CENTER[0] - _FRONT_HALF[0]
    + rail.HOLE_X[RECEIPT_FLAG_HOLE] * _sheet_mm(SHEET_SCALE) + _FLAG_RIM,
    FRONT_CENTER[1] - _FLAG_RIM,
)
# The note's readback envelope: its text cell and the leader up to the rim,
# with a 1 mm reserve round the tip.
RECEIPT_FLAG_ENVELOPE = (
    min(RECEIPT_FLAG_CELL[0], RECEIPT_FLAG_LANDING[0] - 0.001),
    RECEIPT_FLAG_CELL[1],
    RECEIPT_FLAG_CELL[2],
    RECEIPT_FLAG_LANDING[1] + 0.001,
)


def assert_leader_note_landing(
    note: Any, edge_xy: tuple[float, float], text_cell: Box, *, what: str,
) -> None:
    """Read the settled text anchor and both leader endpoints independently:
    the leader runs from inside ``text_cell`` to within 1 mm of ``edge_xy``."""
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    anchor = tuple(float(v) for v in annotation.GetPosition() or ())[:2]
    if len(anchor) != 2 or not _inside((*anchor, *anchor), text_cell):
        raise RuntimeError(f"{what} text left its lane: {anchor!r}")
    if int(annotation.GetLeaderCount()) != 1:
        raise RuntimeError(f"{what} must retain exactly one leader")
    points = tuple(float(v) for v in annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6:
        raise RuntimeError(f"{what} leader is unreadable")
    if len(points) % 3:
        raise RuntimeError(f"{what} leader points are incomplete")
    ends = ((points[0], points[1]), (points[-3], points[-2]))
    if not any(
        _inside((*start, *start), text_cell) and math.dist(tip, edge_xy) <= 0.001
        for start, tip in (ends, ends[::-1])
    ):
        raise RuntimeError(f"{what} leader left its intended feature: {ends!r}")


# View captions (3 mm text, top edge at y, centred on the view): each under
# its view's outline, FRONT's under its stack's flag.
_CAPTION_GAP = 0.0027
CAPTIONS = (
    ("FRONT", FRONT_CENTER[0], RECEIPT_FLAG_CELL[1] - 0.002, SHEET_SCALE),
    (
        "TOP",
        TOP_CENTER[0],
        view_cell(TOP_CENTER, _TOP_HALF)[1] - _CAPTION_GAP,
        SHEET_SCALE,
    ),
    (
        "RIGHT",
        RIGHT_CENTER[0],
        view_cell(RIGHT_CENTER, _RIGHT_HALF)[1] - _CAPTION_GAP,
        PROFILE_SCALE,
    ),
    (
        "ISOMETRIC",
        ISO_CENTER[0],
        view_cell(ISO_CENTER, _ISO_HALF)[1] - _CAPTION_GAP,
        ISO_SCALE,
    ),
)
_CAPTION_HALF_WIDTH = 0.022  # "ISOMETRIC  1:4" at 3 mm is about 33 mm wide
# The member this sheet checks, in the top band; sheet 1 carries its quantity.
ITEM_LABEL = f"{VARIANTS[0][1]}: RECEIPT CHECK"
ITEM_LABEL_XY = (0.050, 0.262)
ITEM_LABEL_CELL = (0.045, 0.252, 0.200, 0.264)


# The end profile at 2:1 is not a projection at the sheet's 1:2, so it is a
# lettered view (rule 9): VIEW B, named by a letter arrow looking along the
# rail at TOP's far (+X) end, right of it and left of the isometric. The
# letter matches draw_fr_tube_frame's VIEW A arrow: 5 mm, its leader
# straight to the end face at mid-height.
END_VIEW_LETTER = "B"
VIEW_LETTER_HEIGHT = 0.005
# The letter's upper-left, from the arrow tip; its readback cell, from the tip.
# A 5 mm "B" is about 4 mm wide: 4 + 4 = 8 mm right of the tip, inside the
# 9.5 mm reach, which ends short of the isometric's cell (TOP's far end stands
# about 10.4 mm left of it).
VIEW_ARROW_TEXT_OFFSET = (0.004, VIEW_LETTER_HEIGHT / 2.0)
VIEW_ARROW_CELL_REACH = (-0.001, -0.005, 0.0095, 0.005)


def caption_text(label: str, scale: tuple[int, int]) -> str:
    """A view's caption: its name, and its scale only where it differs from
    the sheet's (rule 9: a scale equal to the sheet's restates the title
    block)."""
    printed_label = f"VIEW {END_VIEW_LETTER}" if label == "RIGHT" else label
    if tuple(scale) == SHEET_SCALE:
        return printed_label
    return f"{printed_label}  {scale[0]}:{scale[1]}"


def view_arrow_points(top_outline: Box) -> tuple[tuple[float, float], tuple[float, float]]:
    """The VIEW B letter's upper-left and its arrow tip: the tip on TOP's far
    end face at mid-height, read from TOP's native outline less its pad."""
    tip = (top_outline[2] - _OUTLINE_PAD, (top_outline[1] + top_outline[3]) / 2.0)
    return (tip[0] + VIEW_ARROW_TEXT_OFFSET[0], tip[1] + VIEW_ARROW_TEXT_OFFSET[1]), tip


def view_arrow_cell(tip: tuple[float, float]) -> Box:
    left, bottom, right, top = VIEW_ARROW_CELL_REACH
    return (tip[0] + left, tip[1] + bottom, tip[0] + right, tip[1] + top)


def _add_view_arrow(adapter: Any, top: Any) -> tuple[Any, tuple[float, float]]:
    """The letter arrow on TOP's far end that names VIEW B."""
    text_xy, tip_xy = view_arrow_points(_box(top.GetOutline(), label="*Top"))
    note = add_leader_note(
        adapter,
        END_VIEW_LETTER,
        text_xy=text_xy,
        attach_xy=tip_xy,
        view=top,
        label="view B viewing arrow",
        height=VIEW_LETTER_HEIGHT,
    )
    return note, tip_xy


def assert_view_arrow(note: Any, tip_xy: tuple[float, float]) -> None:
    """The arrow's tip still lands on TOP's far end face."""
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    points = tuple(float(v) for v in annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > 0.001:
        raise RuntimeError(f"view B arrow tip left TOP's far end: {points!r}")


def _center_outline(view: Any, name: str, center: tuple[float, float]) -> None:
    position = tuple(float(value) for value in view.Position)
    if len(position) != 2 or not all(map(math.isfinite, position)):
        raise RuntimeError(f"{name}: invalid native view position {position!r}")
    box = _box(view.GetOutline(), label=name)
    target = [
        position[0] + center[0] - (box[0] + box[2]) / 2,
        position[1] + center[1] - (box[1] + box[3]) / 2,
    ]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"{name}: failed to position the view")


def receipt_text_point(
    name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    offset: float,
) -> tuple[float, float]:
    """A dimension's text target: short spans (the station, the end wall)
    outside their left witness, long ones centred, Length shifted to keep its
    measured multiline callout inside its witnesses. ``offset`` is normal to
    the rail."""
    y = (start[1] + end[1]) / 2.0 + offset
    outside = TEXT_OUTSIDE_START.get(name)
    if outside is not None:
        return start[0] - outside, y
    x = (start[0] + end[0]) / 2.0
    if name == "Length":
        x += LENGTH_TEXT_SHIFT
    return x, y


def _receipt_positions(adapter: Any, front: Any) -> dict[str, tuple[float, float]]:
    """Each receipt dimension's text point (``receipt_text_point``) from its
    model stations on the rail's centreline."""
    stations = sorted(
        {x for start, end, _ in RECEIPT_DIMENSIONS.values() for x in (start, end)}
    )
    points = dict(
        zip(
            stations,
            model_points_in_view(
                adapter,
                front,
                [(x / 1000.0, 0.0, 0.0) for x in stations],
                label="rail stations",
                names=[f"x {x:g}" for x in stations],
            ),
            strict=True,
        )
    )
    return {
        name: receipt_text_point(name, points[start], points[end], offset)
        for name, (start, end, offset) in RECEIPT_DIMENSIONS.items()
    }


def _display(annotation: Any) -> Any:
    specific = _early_bound(annotation, "IAnnotation").GetSpecificAnnotation()
    if specific is None:
        raise RuntimeError("receipt dimension has no display dimension")
    return _early_bound(specific, "IDisplayDimension")


def assert_receipt_controls(adapter: Any, annotations: list[Any]) -> None:
    """Every nominal model reference is untoleranced and parenthesised, with
    exactly its authored callouts and arrow side.

    Matching actual hardware is accepted by the fitting instructions."""
    found = {}
    for annotation in annotations:
        found[dimension_name(adapter, annotation)] = _display(annotation)
    if set(found) != set(RECEIPT_DIMENSIONS):
        raise RuntimeError(
            f"receipt dimensions {sorted(found)} != {sorted(RECEIPT_DIMENSIONS)}"
        )
    for name, display in found.items():
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        brackets = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        callout = str(display.GetText(_CALLOUT_BELOW) or "").replace("\r\n", "\n")
        above = str(display.GetText(3) or "").replace("\r\n", "\n")
        expected_above = rail.END_FIT_CALLOUT if name == "Length" else ""
        expected_below = RECEIPT_CALLOUTS_BELOW.get(name, "")
        value = abs(float(dimension.SystemValue))
        expected = RECEIPT_NOMINALS[name]
        if (
            abs(value - expected / 1000.0) > 1e-8
            or int(tolerance.Type) != _TOL_NONE
            or brackets != ("(", ")")
            or callout != expected_below
            or above != expected_above
        ):
            raise RuntimeError(
                f"rail reference {name}: value {value!r}, expected {expected!r}, "
                f"tolerance type {int(tolerance.Type)}, brackets {brackets!r}, "
                f"callout {callout!r}"
            )
        if name == "Length":
            continue
        if int(display.ArrowSide) != RECEIPT_ARROW_SIDES[name]:
            raise RuntimeError(f"rail {name} did not keep its authored arrow side")


@_telemetry.traced("drawing.rail_receipt_dimensions")
def _receipt_dimensions(adapter: Any, front: Any) -> list[Any]:
    """Import the rail's station, end-wall and length dimensions into FRONT."""
    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=_receipt_positions(adapter, front),
        view_label="rail hole face",
        dimensions_by_feature=rail.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, FRONT_DIMENSION_PRECISION)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        set_reference_dimension(adapter, annotation, label=name)
        if name == "Length":
            continue
        display = _display(annotation)
        display.ArrowSide = RECEIPT_ARROW_SIDES[name]
    # Length witnesses identify both actual rail end faces. Put the fit flag
    # above its value, away from the proven eight station-text lanes below.
    set_dimension_callouts(
        adapter, annotations, {"Length": rail.END_FIT_CALLOUT}, location="above"
    )
    # The end wall's acceptance under its value: 2X, the walls at both ends.
    set_dimension_callouts(adapter, annotations, RECEIPT_CALLOUTS_BELOW, location="below")
    assert_receipt_controls(adapter, annotations)
    return annotations


def _horizontal(segment: Segment) -> bool:
    return abs(segment[0][1] - segment[1][1]) < 1e-6


def _vertical(segment: Segment) -> bool:
    return abs(segment[0][0] - segment[1][0]) < 1e-6


def _crosses(segment: Segment, box: Box, *, gap: float) -> bool:
    """``segment`` passes within ``gap`` of ``box``."""
    (x0, y0), (x1, y1) = segment
    return _segment_crosses_box(
        LeaderSegment("", "dim", x0, y0, x1, y1), box, inset=-gap
    )


def receipt_stack_findings(
    inks: dict[str, tuple[Box, list[Segment]]], flag: Box
) -> list[str]:
    """What breaks the receipt stack's spacing rule, from each dimension's
    text box and lines (sheet metres) and the flag note's box.

    Each text sits on its own dimension line: its foot at most
    ``TEXT_ON_LINE_MAX`` over that line, inside the line's run. Its own
    extension lines stay out of it. Every other dimension's text and lines,
    extension lines included, and the flag stay ``CLEAR_GAP_M`` clear of it.
    The station lines step outward from the part in station order, and the
    flag stands under the last one, clear of every line. The end wall is no
    station: it obeys only the clearance rules.
    """
    findings = []
    line_y = {}
    for name, (text, segments) in inks.items():
        horizontal = [segment for segment in segments if _horizontal(segment)]
        if not horizontal:
            findings.append(f"{name} has no dimension line")
            continue
        line = max(horizontal, key=lambda s: abs(s[1][0] - s[0][0]))
        y = line[0][1]
        line_y[name] = y
        # The line's run: every horizontal of its own at its height, so the
        # leg under an outside text counts.
        run = [
            x for segment in horizontal if abs(segment[0][1] - y) < 1e-6
            for x in (segment[0][0], segment[1][0])
        ]
        foot = text[1] - y
        if not -0.0005 <= foot <= TEXT_ON_LINE_MAX:
            findings.append(
                f"{name} text foot stands {foot * 1000:.2f} mm off its own line"
            )
        if text[2] <= min(run) or text[0] >= max(run):
            findings.append(f"{name} text is not over its own line")
        for segment in segments:
            length = math.dist(*segment)
            if _vertical(segment) and length > 0.003 and _crosses(segment, text, gap=0.0):
                findings.append(f"{name} text sits on its own extension line")
        for other, (other_text, other_segments) in inks.items():
            if other == name:
                continue
            if name < other and not boxes_clear(text, other_text):
                findings.append(f"{name} text and {other} text overlap")
            if any(_crosses(s, text, gap=CLEAR_GAP_M) for s in other_segments):
                findings.append(f"{other} line runs within {CLEAR_GAP_M * 1000:.0f} mm of {name} text")
        if not boxes_clear(text, flag):
            findings.append(f"{name} text and the flag overlap")
        if any(_crosses(segment, flag, gap=0.001) for segment in segments):
            findings.append(f"{name} line runs into the flag")
    stations = [line_y[name] for name in rail.STATION_DIMENSIONS if name in line_y]
    if any(b >= a - CLEAR_GAP_M for a, b in zip(stations, stations[1:])):
        findings.append(f"station lines do not step outward: {stations}")
    if stations and flag[3] >= stations[-1]:
        findings.append("the flag is not under the last station line")
    return findings


def _receipt_ink(annotation: Any, *, label: str) -> tuple[Box, list[Segment]]:
    """A receipt dimension's rendered text block, boxed from every text run it
    draws (value, tolerance) by the layout audit's estimator, and its lines."""
    data = _early_bound(_display(annotation).GetDisplayData(), "IDisplayData")
    boxes = []
    for index in range(int(data.GetTextCount())):
        text = str(data.GetTextAtIndex(index) or "")
        if not text.strip():
            continue
        anchor = [float(value) for value in data.GetTextPositionAtIndex(index)]
        reference = int(data.GetTextRefPositionAtIndex(index))
        box = estimate_text_box(
            text,
            anchor=(anchor[0], anchor[1]),
            height=float(data.GetTextHeightAtIndex(index)),
            reference=reference if 0 <= reference <= 5 else 0,
            angle=float(data.GetTextAngleAtIndex(index)),
        )
        if box is not None:
            boxes.append(box)
    if not boxes:
        raise RuntimeError(f"rail {label} draws no text to measure")
    text_box = (
        min(box.xmin for box in boxes),
        min(box.ymin for box in boxes),
        max(box.xmax for box in boxes),
        max(box.ymax for box in boxes),
    )
    segments = dimension_segments(annotation)
    _telemetry.info(
        f"rail {label} ink: text=({', '.join(f'{v:.4f}' for v in text_box)}) "
        f"lines={[tuple(round(v, 4) for p in s for v in p) for s in segments]}"
    )
    return text_box, segments


def assert_receipt_stack_clear(adapter: Any, annotations: list[Any], flag: Box) -> None:
    """The rendered stack obeys ``receipt_stack_findings``. Never moves ink."""
    inks = {}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        inks[name] = _receipt_ink(annotation, label=name)
    findings = receipt_stack_findings(inks, flag)
    if findings:
        raise RuntimeError("rail receipt stack: " + "; ".join(findings))


def _source_properties(model: Any) -> dict[str, str]:
    """The source's sheet-2 facts, its member notes the specs' own."""
    properties = read_required_properties(
        model, SOURCE_PROPERTIES, required=SOURCE_PROPERTIES
    )
    for name, expected in NOTE_PROPERTIES.items():
        if properties[name].replace("\r\n", "\n") != expected:
            raise RuntimeError(f"{PART_STEM}: stale source note {name!r}")
    return properties


def append_rail_receipt_sheet(adapter: Any) -> tuple[Callable[[], None], ...]:
    """Author RAIL RECEIPT: the Rail member's views, references and flag."""
    draw = adapter.currentModel
    document = _early_bound(draw, "IDrawingDoc")
    if not document.ActivateSheet(RECEIPT_SHEET_NAME):
        raise RuntimeError("failed to activate the rail RECEIPT sheet")
    sheet = _early_bound(document.GetCurrentSheet(), "ISheet")

    views = {}
    with _telemetry.span("drawing.rail_views"):
        for name, center, _, scale in VIEWS:
            view = _early_bound(
                place_view(adapter, str(SOURCE), name, *center, scale=scale), "IView"
            )
            views[name] = view
        configure_reference_views(adapter, rail.CONFIGURATION, list(views.values()))
        # A prism with plain holes: no hidden edge names a feature.
        for view in views.values():
            set_hidden_lines_removed(adapter, view)
        # Later insertions may drift the sheet scale; pin each view explicitly.
        for name, _, _, scale in VIEWS:
            views[name].UseSheetScale = 0
            views[name].ScaleRatio = double_array([float(value) for value in scale])
        _rebuild(draw, phase="rail view extents")
        for name, center, _, _ in VIEWS:
            _center_outline(views[name], name, center)
        _rebuild(draw, phase="centre rail views")
        # Before any annotation: GetOutline grows to take a view's own.
        for name, center, half, _ in VIEWS:
            box = _box(views[name].GetOutline(), label=name)
            if not _inside(box, view_cell(center, half)):
                raise RuntimeError(f"{name}: rail view leaves its cell: {box!r}")
        _center_marks_without_lines(
            [views[name] for name, _, _, _ in VIEWS],
            tuple((name, center, None) for name, center, _, _ in VIEWS),
        )
    front = views["*Front"]
    sheet.CustomPropertyView = view_name(adapter, front)
    properties = _source_properties(_early_bound(front.ReferencedDocument, "IModelDoc2"))

    annotations = _receipt_dimensions(adapter, front)

    notes = []
    with _telemetry.span("drawing.rail_annotations"):
        centred = [
            (caption_text(label, scale), x, y, (
                x - _CAPTION_HALF_WIDTH, y - 0.006, x + _CAPTION_HALF_WIDTH, y + 0.001
            ))
            for label, x, y, scale in CAPTIONS
        ]
        for text, x, y, box in centred:
            note = _literal_note(adapter, text, x, y)
            bounds = _box(note.GetExtent(), label=text, kind="note")
            annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
            if not annotation.SetPosition(2 * x - (bounds[0] + bounds[2]) / 2, y, 0.0):
                raise RuntimeError(f"{text}: failed to centre the note")
            notes.append((note, text, text, box))
        flag_note = add_attached_note(
            adapter, front, text=rail.RECEIPT_FLAG, entity_xy=RECEIPT_FLAG_LANDING,
            note_xy=RECEIPT_FLAG_ANCHOR, label="rail hole pattern",
        )
        notes.append((flag_note, rail.RECEIPT_FLAG, rail.RECEIPT_FLAG, RECEIPT_FLAG_ENVELOPE))
        note = _literal_note(adapter, ITEM_LABEL, *ITEM_LABEL_XY)
        notes.append((note, ITEM_LABEL, ITEM_LABEL, ITEM_LABEL_CELL))
        arrow_note, arrow_tip = _add_view_arrow(adapter, views["*Top"])
        notes.append(
            (arrow_note, END_VIEW_LETTER, END_VIEW_LETTER, view_arrow_cell(arrow_tip))
        )
        title_notes = _purchased_title_block(
            adapter,
            draw,
            material=properties["Material Specification"],
            finish=properties["Finish"],
            material_property="Material Specification",
        )
    _rebuild(draw, phase="rail receipt notes")
    title_fit = fit_purchased_title_block(adapter, spec=SPEC)

    def settled() -> None:
        if not document.ActivateSheet(RECEIPT_SHEET_NAME):
            raise RuntimeError("failed to activate the rail RECEIPT sheet for readback")
        template = DRAWING_TEMPLATES[SPEC.layout]
        region = sheet_drawable_region(
            adapter, sheet, width=template.width_m, height=template.height_m
        )
        border = (region.xmin, region.ymin, region.xmax, region.ymax)
        for name, _, _, scale in VIEWS:
            view = views[name]
            if (
                str(view.ReferencedConfiguration) != rail.CONFIGURATION
                or Path(view.GetReferencedModelName()).resolve() != SOURCE.resolve()
                or tuple(view.ScaleRatio) != tuple(float(value) for value in scale)
            ):
                raise RuntimeError(f"{name}: rail receipt view source/member/scale changed")
            box = _box(view.GetOutline(), label=name)
            if not _inside(box, border):
                raise RuntimeError(f"{name}: rail view leaves the border: {box!r}")
        _source_properties(_early_bound(front.ReferencedDocument, "IModelDoc2"))
        assert_receipt_controls(adapter, annotations)
        for note, linked_text, resolved_text in title_notes:
            if (
                note.PropertyLinkedText != linked_text
                or note.GetText().replace("\r\n", "\n") != resolved_text
            ):
                raise RuntimeError(
                    "rail receipt title-block property did not resolve from its "
                    f"expected source: {linked_text!r}"
                )
        for note, linked_text, resolved_text, cell in notes:
            actual_link = note.PropertyLinkedText
            actual_text = note.GetText().replace("\r\n", "\n")
            if actual_link != linked_text or actual_text != resolved_text:
                raise RuntimeError(
                    f"rail note readback mismatch: expected link={linked_text!r}, "
                    f"actual link={actual_link!r}, expected text={resolved_text!r}, "
                    f"actual text={actual_text!r}"
                )
            box = _box(note.GetExtent(), label=linked_text, kind="note")
            if not _inside(box, cell) or not _inside(box, border):
                raise RuntimeError(
                    f"rail note leaves its reserved space/border: {linked_text!r}: {box!r}"
                )
        title_fit()
        assert_view_arrow(arrow_note, arrow_tip)
        assert_leader_note_landing(
            flag_note, RECEIPT_FLAG_LANDING, RECEIPT_FLAG_CELL, what="rail hole pattern callout",
        )
        # The stack rule reads the flag's text: its extent less the leader's
        # rise to the rim, which stands over the text's top.
        flag_extent = _box(flag_note.GetExtent(), label=rail.RECEIPT_FLAG, kind="note")
        assert_receipt_stack_clear(
            adapter,
            annotations,
            (*flag_extent[:3], min(flag_extent[3], RECEIPT_FLAG_CELL[3])),
        )

    settled()
    return (settled,)


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_variant_drawing(
        adapter,
        SPEC,
        variants=VARIANTS,
        item=ITEM,
        purchase_unit=PURCHASE_UNIT,
        general_text=GENERAL_TEXT,
        notes=FOOTER_NOTES,
        additional_sheet_scales={RECEIPT_SHEET_NAME: SHEET_SCALE},
        append_sheets=append_rail_receipt_sheet,
        additional_sheets_title="Rail Receipt Check",
        title_fit=True,
        isometric_only=ISOMETRIC_ONLY,
        unit=part_drawing_unit(PART_STEM),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
