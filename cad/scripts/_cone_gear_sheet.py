"""Front-view sheet helpers the cone gears' drawings share.

The cone-gear family (MHA-DT-03, draw_dt_cone_gear) and the cone tip gear
(MHA-DT-37, draw_dt_cone_tip_gear) print the same front-view inspection
layout: the root envelope's limit stack right of the tip circle, the circular
tooth thickness on the +X tooth with its text offset onto its own shelf under
that stack, and the printed-ink audit that keeps every line off that text.
Both also letter detail boundaries and title views with notes centred by
their extent. The layout lives here once, so a fix to one sheet reaches the
other.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    view_name,
)

import _telemetry
from _com import _early_bound
from _drawing_annotation_extent import callout_ink, move_annotation
from _drawing_common import rebuild_drawing
from _drawing_dimensions import offset_dimension_text
from _drawing_leaders import ARROW_TEXT_CLEARANCE, dimension_segments
from _layout_geometry import Box, Segment, segment_box_distance
from _pdf_ink import PageInk

# The functional root-envelope stack stands right of the tip circle,
# above the thickness witness and the thickness text's shelf
# (``tooth_thickness_shelf``), and clear of the side
# view (left edge >= 0.219 on every sheet). The gap was sized for a mate's row
# ~4 chars wider than the label (centred block); the note flag under the label
# is narrower, so the block's left edge stands farther from the teeth.
FLOOR_DIA_GAP_X = 0.0215
# The shelf's rise above 0.6 of the tip radius: 6 mm with the three-row stack;
# the row under the label (centred block) would lower it ~2.8 mm.
FLOOR_DIA_RISE = 0.009
# The thickness dimension's arrows stand outside its witnesses, so the upper
# arrow's tail runs UP the stack's lane: on the 834-fix-6927 T006 sheet (8:1)
# it crossed the shelf under "GAP FLOOR" by ~1 mm.  The shelf therefore rises
# per sheet to clear that tail (``floor_dia_y``).
#
# swUserPreferenceDoubleValue_e.swDetailingArrowLength (swconst.tlb R2026x),
# read with swDetailingNoOptionSpecified: how far the dimension line runs past
# an outside arrow's tip, head and tail together.
_PREF_ARROW_LENGTH = 26
_PREF_OPT_NONE = 0
# The project DRWDOT's value (0.25 in).  The 834-fix-6927 T006 sheet prints
# the thickness arrow 6.35 mm from tip to tail end; build() reads the live
# preference and refuses a template that differs.
DIMENSION_ARROW_LENGTH = 0.00635
# The limit stack hangs ~11 mm from its anchor down to the shelf line (four
# rows, the label and the mate under the limits, at the ~5.7 mm pitch of the
# ENFORCE round-1 T084 render's three-row block), rounded outward; it is
# centred on the anchor, so the same half-height bounds its top.
FLOOR_STACK_HALF_HEIGHT = 0.0115
# The thickness text stands on its own shelf right of the +X tooth, under the
# root-envelope stack. Hung off its dimension line (horizontal text outside
# the witnesses), the block started AT that line, so the line dropping from
# the 3 o'clock tooth ran down the C of CIRCULAR, 0.19 mm of air on every
# sheet (machinist review of 2056e3344, rule 14). The text is offset
# (OffsetText): the line stays at the tooth, and its leader leaves the line's
# midpoint for the shelf's near end, closing on the block's lower-left
# corner from up-left. This gap keeps that leader 2.7 mm off the C on the
# steepest sheet (T012), and the block's right end 3.2 mm left of the side
# view on the tightest (T084), replayed on that run's printed ink.
TOOTH_THICKNESS_TEXT_GAP = 0.0065
# The shelf stands this far under the root-envelope anchor: the block's ink,
# 24.7 mm from shelf to top row on every sheet of run 20261024T091056564Z,
# then tops out 3.3 mm under that stack's shelf, which printed 10.1 mm under
# its anchor.
TOOTH_THICKNESS_SHELF_DROP = 0.038
# Offset text is centred on its position (_drawing_annotation_extent). The
# seed puts that centre half the 64.2 mm shelf right of, and 12.9 mm above,
# the shelf's start (run 20261024T091056564Z); the measured shelf then
# corrects it to within the tolerance.
TOOTH_THICKNESS_SEED = (0.0321, 0.0129)
TOOTH_THICKNESS_PLACE_TOL = 0.0002
# Printed air the exported PDF must keep between the callout's glyphs and
# every line but its own shelf: the fleet's arrow-to-text clearance.
TOOTH_THICKNESS_TEXT_AIR = ARROW_TEXT_CLEARANCE
# How far round the callout's text block a line is still measured; anything
# farther is reported at this distance.
_TEXT_AIR_WINDOW = 0.010
# A centred note must land within this of its place.
NOTE_CENTRING_TOL_M = 0.001
# The letters print at the notes' height: at the default 3.5 mm, A's would
# not fit the narrowest web between its boundary and the root envelope.
DETAIL_LETTER_HEIGHT = 0.0025
# Letter centre beyond its boundary: half the letter's ~2.6 mm diagonal
# extent plus ~1 mm of air.
DETAIL_LETTER_REACH = 0.0025


def thickness_arrow_reach_y(axis_y: float, half_thickness: float) -> float:
    """Sheet y where the thickness dimension's upper arrow tail ends.

    The upper witness stands ``half_thickness`` (sheet metres: half the arc
    thickness, an upper bound on the pitch chord it witnesses) above the
    bore axis at ``axis_y``, and one outside arrow runs on past it.
    """
    return axis_y + half_thickness + DIMENSION_ARROW_LENGTH


def floor_dia_y(axis_y: float, half_od: float, half_thickness: float) -> float:
    """Anchor y of the root-envelope stack: its usual place above the
    thickness witness, raised where that would put the shelf within the
    fleet's arrow-to-text clearance of the thickness arrow's tail."""
    usual = axis_y + 0.6 * half_od + FLOOR_DIA_RISE
    lowest = (
        thickness_arrow_reach_y(axis_y, half_thickness)
        + ARROW_TEXT_CLEARANCE
        + FLOOR_STACK_HALF_HEIGHT
    )
    return max(usual, lowest)


def tooth_thickness_shelf(line_x: float, floor_y: float) -> tuple[float, float]:
    """Sheet point where the thickness text's shelf starts: the text gap
    right of its dimension line at ``line_x``, the shelf drop under the
    root-envelope stack's anchor at ``floor_y``."""
    return line_x + TOOTH_THICKNESS_TEXT_GAP, floor_y - TOOTH_THICKNESS_SHELF_DROP


def assert_dimension_arrow_length(drawing: Any) -> None:
    """Refuse a template whose arrow length is not the one the layout assumes."""
    extension = _early_bound(
        _early_bound(drawing, "IModelDoc2").Extension, "IModelDocExtension"
    )
    live = float(extension.GetUserPreferenceDouble(_PREF_ARROW_LENGTH, _PREF_OPT_NONE))
    if abs(live - DIMENSION_ARROW_LENGTH) > 1e-6:
        raise RuntimeError(
            f"drawing arrow length reads {live * 1000.0:.3f} mm; the root-envelope "
            f"stack is placed for {DIMENSION_ARROW_LENGTH * 1000.0:.3f} mm"
        )
    _telemetry.info(f"drawing arrow length {live * 1000.0:.3f} mm")


def shelve_tooth_thickness(
    adapter: Any,
    annotations: list[Any],
    *,
    line_x: float,
    target: tuple[float, float],
    label: str,
) -> None:
    """Offset the thickness text onto its own shelf, starting at ``target``
    (``tooth_thickness_shelf``), and prove the shelf landed there while the
    line stayed at the tooth, at ``line_x``.

    The line keeps the pre-offset anchor's x (the oblique jig's handoff in
    solidworks-drawing-layout-tuning.md); the text is seeded from the last
    print's block, then moved by what its own native shelf reads.
    """
    matches = [
        _early_bound(annotation, "IAnnotation")
        for annotation in annotations
        if dimension_name(adapter, annotation) == "ToothThickness"
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: expected one ToothThickness, found {len(matches)}"
        )
    annotation = matches[0]
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    seed = (target[0] + TOOTH_THICKNESS_SEED[0], target[1] + TOOTH_THICKNESS_SEED[1])
    offset_dimension_text(adapter, [annotation], {"ToothThickness": seed})
    ink = callout_ink(adapter, annotation, label=label)
    dx, dy = target[0] - ink.text[0], target[1] - ink.text[1]
    if max(abs(dx), abs(dy)) > TOOTH_THICKNESS_PLACE_TOL:
        move_annotation(adapter, annotation, dx, dy, label=label)
        ink = callout_ink(adapter, annotation, label=label)
    error = (ink.text[0] - target[0], ink.text[1] - target[1])
    stations = sorted(
        round(start[0], 6)
        for start, end in dimension_segments(annotation)
        if abs(start[0] - end[0]) < 1e-7
    )
    _telemetry.info(
        f"{label}: thickness shelf starts ({ink.text[0] * 1000:.2f}, "
        f"{ink.text[1] * 1000:.2f}) mm for ({target[0] * 1000:.2f}, "
        f"{target[1] * 1000:.2f}); vertical lines at "
        f"{[round(x * 1000, 2) for x in stations]} mm, "
        f"line anchor {line_x * 1000:.2f}",
        offset_text=bool(display.OffsetText),
    )
    if not bool(display.OffsetText):
        raise RuntimeError(f"{label}: the thickness text did not stay offset")
    if max(map(abs, error)) > TOOTH_THICKNESS_PLACE_TOL:
        raise RuntimeError(
            f"{label}: thickness shelf starts {error[0] * 1000:.2f}, "
            f"{error[1] * 1000:.2f} mm off its place"
        )
    strayed = [x for x in stations if abs(x - line_x) > TOOTH_THICKNESS_PLACE_TOL]
    if not stations or strayed:
        raise RuntimeError(
            f"{label}: the thickness line left the tooth: vertical lines at "
            f"{[round(x * 1000, 2) for x in stations]} mm, "
            f"anchor {line_x * 1000:.2f}"
        )


def tooth_thickness_text_air(
    page: PageInk, rows: tuple[str, ...], *, sheet: str
) -> tuple[float, str]:
    """The smallest printed air between the thickness callout's glyphs and
    any line on ``page`` (sheet ``sheet``) other than the shelf the text
    stands on, with the nearest line.

    The callout is its printed ``rows`` other than the value, top down (one
    PDF text run each), and every run inside their joint box (the value and
    its tolerance). Its name over the value prints once a page; its "SEE NOTE
    2" flag also prints on the tip diameter and on the root envelope (whose
    block stands just above this one), so the flag is the nearest such run
    under the name. Its shelf is the horizontal line under that box spanning
    it. Air is the glyph-box to line distance less half the stroke width.
    """

    def printed(row: str) -> list[Any]:
        key = "".join(row.split())
        return [span for span in page.spans if "".join(span.text.split()) == key]

    name_row, *lower_rows = rows
    names = printed(name_row)
    if len(names) != 1:
        alike = [span.text for span in page.spans if span.text[:6] == name_row[:6]]
        raise ValueError(
            f"{sheet}: thickness row {name_row!r} printed {len(names)} times "
            f"(runs starting alike: {alike})"
        )
    name = names[0]
    name_x = (name.xmin + name.xmax) / 2.0
    runs = [name]
    for row in lower_rows:
        found = [span for span in printed(row) if span.ymax <= name.ymin]
        if not found:
            raise ValueError(
                f"{sheet}: thickness row {row!r} printed 0 times under {name_row!r}"
            )
        runs.append(
            min(
                found,
                key=lambda span: math.hypot(
                    (span.xmin + span.xmax) / 2.0 - name_x, name.ymin - span.ymax
                ),
            )
        )
    block = Box(
        min(span.xmin for span in runs),
        min(span.ymin for span in runs),
        max(span.xmax for span in runs),
        max(span.ymax for span in runs),
    )
    hair = 0.0001
    glyphs = [
        Box(glyph.xmin, glyph.ymin, glyph.xmax, glyph.ymax)
        for span in page.spans
        if block.xmin - hair <= span.xmin
        and span.xmax <= block.xmax + hair
        and block.ymin - hair <= span.ymin
        and span.ymax <= block.ymax + hair
        for glyph in span.glyphs
    ]
    near = Box(
        block.xmin - _TEXT_AIR_WINDOW,
        block.ymin - _TEXT_AIR_WINDOW,
        block.xmax + _TEXT_AIR_WINDOW,
        block.ymax + _TEXT_AIR_WINDOW,
    )
    shelves = 0
    air, nearest = _TEXT_AIR_WINDOW, "no line within reach"
    for stroke in page.strokes:
        if not (stroke.stroked or stroke.filled):
            continue
        segment = Segment(stroke.x0, stroke.y0, stroke.x1, stroke.y1)
        if segment.length == 0.0 or segment_box_distance(segment, near) > 0.0:
            continue
        if (
            abs(stroke.y0 - stroke.y1) < 1e-7
            and block.ymin - 0.0025 <= stroke.y0 <= block.ymin
            and min(stroke.x0, stroke.x1) <= block.xmin + 0.0005
            and max(stroke.x0, stroke.x1) >= block.xmax - 0.0005
        ):
            shelves += 1
            continue
        pen = stroke.width / 2.0 if stroke.stroked else 0.0
        for glyph in glyphs:
            gap = segment_box_distance(segment, glyph) - pen
            if gap < air:
                air = gap
                nearest = (
                    f"{gap * 1000:.2f} mm from line {segment.format_mm()} to glyph "
                    f"{glyph.format_mm()}"
                )
    if not shelves:
        raise ValueError(
            f"{sheet}: no shelf under the thickness text {block.format_mm()}"
        )
    return air, nearest


def activate_view(adapter: Any, view: Any, *, label: str) -> str:
    """Make ``view`` the active view (sketch entities and notes land in it)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def sketch_view_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    add_to_db: bool,
    label: str,
) -> Any:
    """Sketch a circle in the ACTIVE ``view``'s own sketch from sheet points,
    through the view sketch's ModelToSketchTransform (draw_ch_amplitude_bar's
    ``_sketch_circle``). Without ``add_to_db`` the circle is left selected,
    which is what Crop2 consumes."""
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = add_to_db
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the {label} circle")
    return circle


@dataclass(frozen=True)
class FrontDetail:
    """A detail boundary on a sheet's front view and where its letter stands.

    ``centre_mm`` and ``radius_mm`` are model millimetres in the front view's
    plane (gear axis at the origin, tooth zero on +X); the letter's centre
    stands ``letter_reach`` (sheet metres) outside the boundary at
    ``letter_angle_deg`` round the boundary's centre.
    """

    letter: str
    centre_mm: tuple[float, float]
    radius_mm: float
    letter_angle_deg: float
    letter_reach: float


def detail_letter_xy(
    detail: FrontDetail, centre: tuple[float, float], radius: float
) -> tuple[float, float]:
    """Sheet centre of ``detail``'s letter round a boundary drawn at sheet
    ``centre`` with sheet ``radius``."""
    angle = math.radians(detail.letter_angle_deg)
    reach = radius + detail.letter_reach
    return centre[0] + reach * math.cos(angle), centre[1] + reach * math.sin(angle)


def note_box(note: Any, *, label: str) -> tuple[float, float, float, float]:
    """``INote.GetExtent``'s lower-left and upper-right corners, sheet metres."""
    values = tuple(float(value) for value in (note.GetExtent() or ()))
    if len(values) != 6 or not all(map(math.isfinite, values)):
        raise RuntimeError(f"{label}: invalid note extent {values!r}")
    box = (values[0], values[1], values[3], values[4])
    if box[0] >= box[2] or box[1] >= box[3]:
        raise RuntimeError(f"{label}: empty note extent {values!r}")
    return box


def set_note_height(note: Any, height: float, *, label: str) -> None:
    """Set a note's character height (add_property_linked_note's form)."""
    annotation = _early_bound(
        _early_bound(note, "INote").GetAnnotation(), "IAnnotation"
    )
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label}: note has no text format")
    text_format.CharHeight = float(height)
    if annotation.SetTextFormat(0, False, text_format) is not True:
        raise RuntimeError(f"{label}: failed to set the note's text height")


def centred_view_note(
    adapter: Any,
    view: Any,
    text: str,
    *,
    center_x: float,
    top: float | None = None,
    center_y: float | None = None,
    height: float | None = None,
    label: str,
) -> None:
    """Insert a note ``view`` owns, centred on ``center_x`` by its extent;
    ``top`` pins its top edge, ``center_y`` its middle (draw_ch_amplitude_bar's
    ``_centred_view_note``). A note that does not centre, or lands in another
    view, raises."""
    if (top is None) == (center_y is None):
        raise ValueError(f"{label}: give the note a top edge or a centre height")
    activate_view(adapter, view, label=label)
    raw = add_note(adapter, text, center_x, top if top is not None else center_y)
    if raw is None:
        raise RuntimeError(f"failed to add the {label} note")
    note = _early_bound(raw, "INote")
    if height is not None:
        set_note_height(note, height, label=label)
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")

    def error_of(box: tuple[float, float, float, float]) -> tuple[float, float]:
        if top is not None:
            return (box[0] + box[2]) / 2.0 - center_x, box[3] - top
        return (box[0] + box[2]) / 2.0 - center_x, (box[1] + box[3]) / 2.0 - center_y

    for _ in range(2):
        error = error_of(note_box(note, label=label))
        if max(abs(error[0]), abs(error[1])) <= NOTE_CENTRING_TOL_M / 10.0:
            break
        position = tuple(float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(
            position[0] - error[0], position[1] - error[1], 0.0
        ):
            raise RuntimeError(f"failed to centre the {label} note")
        rebuild_drawing(adapter, label=f"{label} note")
    error = error_of(note_box(note, label=label))
    if max(abs(error[0]), abs(error[1])) > NOTE_CENTRING_TOL_M:
        raise RuntimeError(
            f"{label} note did not centre: off by ({error[0] * 1000:.2f}, "
            f"{error[1] * 1000:.2f}) mm"
        )
    first_words = text.split("\n")[0].split()
    owned = [
        str(_early_bound(found, "INote").GetText() or "").split()
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if sum(words[: len(first_words)] == first_words for words in owned) != 1:
        raise RuntimeError(f"{label} note did not land in its view: {owned!r}")
