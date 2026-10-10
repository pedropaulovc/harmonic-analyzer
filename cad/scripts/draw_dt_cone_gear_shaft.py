r"""Create the cone-gear-shaft manufacturing drawing under the simplicity policy.

The turned shaft is shown horizontally at 1:1 with baseline lengths from the
collar's thrust face below it and every diameter above it on that same side
view, each dimension line inside the land it measures (the 3.2 mm collar
instead takes one near-side arrow on its rim).  The two short lands
ahead of the tip are 6.9 mm long, so the three tip-end diameter texts climb
in steps: the tip's line rises highest and each text hangs to the RIGHT of
its line above every line it spans.  Each gear land's D-flat is shown in its
own enlarged cut-only section, A-A to D-D, carrying its across-flat; B-B to
D-D are cut on DETAIL E, the stepped tip at 4:1, where their arrows and
letters have room.  A standard isometric supplies pictorial clarity, and the
note names the bores the seats and flats mate and the tailstock support the
tip land needs (U40).  Source geometry and native model fits stay
authoritative: the sheet types no tolerance and no precision.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_cone_gear_shaft.py dt-cone-gear-shaft
"""

from __future__ import annotations

import argparse
import math
import sys
from enum import Enum
from typing import Any, NamedTuple

from collections.abc import Iterable, Mapping, Sequence

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
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
    model_points_in_view,
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
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _layout_geometry import estimate_text_box
from _surface_finish import surface_finish_by_key
from cone_shaft_land_bands import TERMINAL_FLAT_EDGE_BREAK_MAX
from dt_cone_gear_shaft_spec import (
    COLLAR_DIA,
    COLLAR_END_STATION,
    COLLAR_STOCK_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_REFERENCE_PRECISION,
    FILLET_CALLOUT,
    FLAT_LANDS,
    JOURNAL_DIA,
    SECTION_DIAS,
    SECTION_ENDS,
    SHAFT_LENGTH,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    delete_view,
    iter_views,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["dt_cone_gear_shaft"]
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
# y < ~0.066).  The spec-derived shaft at 1:1 ends at BIG_END_X, leaving the
# right third for the pictorial (top) over the four D sections; the tip
# detail fills the field above the side view (codex review, #1128: with the
# sections in one row the drawing sat in the lower half, the upper field
# empty, and the row's captions ran onto the title block).  The group sits
# just below mid-height so the baseline stack below and the diameters above
# share the field with the note block in the lower left (review 2026-09-23:
# at 0.170 rows A-B stood empty but for the note).  The view is placed by its
# large end: every dimension below is laid out from that datum face, so a
# change at the tip (the 2026-09-29 prism tip block lengthened it 2.31 mm)
# moves only the tip.
BIG_END_X = 0.2526
SIDE_CENTER = (BIG_END_X - SHAFT_LENGTH / 2000.0, 0.150)
TIP_END_X = BIG_END_X - SHAFT_LENGTH / 1000.0
ISO_CENTER = (0.363, 0.232)
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
    "ShoulderR": (BIG_END_X - SECTION_ENDS[1] / 1000.0 + 0.010, 0.1640),
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
# land it measures; the short lands' lines follow their current end stations,
# one third of a land length back from each small end.  Ø12.231 stands just
# off the faced end.  A tip-end text spans its right-hand neighbours'
# lines: the tip's text sits highest and each neighbour to the right steps
# down, so no line rises through a text (codex, 18395f30).  Lands 2 and 3
# carry their lines mid-land; the tip's line stays 1.7 mm in from the tip
# face, right of the tip finish glyph, and follows the tip face when its
# station moves.
SIDE_DIAMETERS = {
    "Sec0Dia": (0.2700, 0.1620),
    "Sec1Dia": (0.1400, 0.1730),
    "Sec2Dia": (BIG_END_X - (2.0 * SECTION_ENDS[2] + SECTION_ENDS[1]) / 3000.0, 0.1760),
    "Sec3Dia": (BIG_END_X - (2.0 * SECTION_ENDS[3] + SECTION_ENDS[2]) / 3000.0, 0.1880),
    "Sec4Dia": (TIP_END_X + 0.0017, 0.2000),
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


class CutParent(Enum):
    """The view a D section's cutting-plane line is drawn on."""

    SIDE = "side view"
    TIP_DETAIL = "tip detail"


class DSection(NamedTuple):
    """One gear land's D-flat section: the station its cutting line crosses,
    the view carrying that line, how far the line reaches either side of the
    axis on that view's sheet, where the removed section stands, and its own
    scale."""

    land: int
    label: str
    station_mm: float
    parent: CutParent
    reach: float
    centre: tuple[float, float]
    scale: tuple[int, int]


# The stepped tip (lands 2..4) is too short at 1:1
# for three cutting lines: an arrow is 12 mm long and its letter stands 14..21
# mm past the line, so B, C and D piled onto each other, onto the tip's
# diameter lines and onto R0.10 3X (codex review, #1128).  They are cut on
# DETAIL E instead, the tip at 4:1 in the empty field above the side view,
# where their lines stand 27 and 28 mm apart.  The detail carries no dimension:
# DragModelDimension refuses to re-home a model dimension into a detail view,
# so every diameter and station stays on the side view.  The circle on the
# side view spans lands 2..4 only, clear of
# the R0.10 leader at the Ø6.350 to Ø9.525 step; the detail draws no boundary
# round its clipped geometry.
TIP_DETAIL_LABEL = "E"
TIP_DETAIL_SCALE = (4, 1)
TIP_DETAIL_STATION_MM = SECTION_ENDS[3] - 1.8
TIP_DETAIL_RADIUS = 0.009
TIP_DETAIL_CENTER = (0.100, 0.236)
# The circle's letter on the side view: up-left of the circle (x 0.069..0.087,
# y 0.141..0.159), between the terminal and Ø3.175 dimension lines,
# under their texts, 2 mm off the circle whichever corner of the
# letter SolidWorks anchors.
TIP_DETAIL_LETTER_XY = (0.064, 0.164)
CUT_PARENT_SCALE = {CutParent.SIDE: SIDE_SCALE, CutParent.TIP_DETAIL: TIP_DETAIL_SCALE}
# A cutting line on the detail spans its land, not the detail's whole view, so
# SolidWorks leaves the full section open (leaf 20260929T212413Z-1-c1463903:
# B-B "did not close"); it is made a partial section, as
# draw_cone_swing_platform cut C-C from its detail.  The line still runs past
# its land on both sides, so the partial cut is the whole D.
PARTIAL_CUT_PARENTS = frozenset({CutParent.TIP_DETAIL})

# The D sections (user ruling 2026-09-28: every gear land carries one flat on
# the shaft's +X).  The side view looks straight at the flats, so their size
# is only readable end-on: each land is cut across and shown cut-only
# (nothing beyond the plane prints), each enlarged to about 16..19 mm across
# so the reader-owned smallest AF reads with its band. A-A cuts land
# 1 on the side view, left of the Ø9.525 line. Its lower letter's top stands
# 4.8..6.3 mm above the line's end, by seat (6.3 on swmaker00000a in the
# 19e33c6c2 build, where a 12.5 mm reach left it 1.4 mm under land 1); the
# 15 mm reach leaves the worst 3.9 mm under the land.  B, C and D cut the
# detail.  A line's arrows look toward the big end (sheet +x) and its
# letter's right edge lands 19.9..21.3 mm past the line, a spread SolidWorks
# sets per line and per seat (leaves 20260929T221513Z-1-22b951a7,
# 20260929T235413Z-1-6ebc5952), so side by side
# the lines must stand at least 23 mm (that run and the next arrow's 1.7 mm
# half-width) plus the layout audit's 2 mm apart.  The three stations are
# spread over their lands for that: B and C 0.6 and 0.8 mm short of the step
# at their land's small end, D 8.0 mm past the detail's centre and inside its
# circle, so the lines stand 26.8 and 28.0 mm apart at 4:1: C's letters clear
# B's arrows by 3.8 mm and D's clear C's by 5.0 mm on the worst seat measured,
# and B's letters clear land 1 by 3.7 mm.  At the old 24 mm (C on the
# detail's centre) D's letter crowded C's arrow at 1.7 mm on swmaker00000f.
# B's reach puts its lower letter 3.5 mm under land 2 and C's matches it; D's,
# on the thinnest land, is shorter.  The four stand in two rows right of the
# side view, under the pictorial, each over its caption, the bottom row's
# captions above the title block (x > 0.216, y < 0.066).  D's across-flat
# carries the torque-corner callout, centred over D's text and
# TORQUE_CALLOUT_REACH either side of it, so D stands between C-C's outline
# and the right border; C stands left of A's column, its cell clear of that
# callout and of the side view's big end.
# The across-flat is the part's own dimension (Sec{i}AF, sketched on the
# land's end plane, parallel to the cut), so it prints its model band.
D_SECTIONS = (
    DSection(
        1, "A", SECTION_ENDS[1] - 25.0, CutParent.SIDE, 0.0150, (0.337, 0.165), (2, 1)
    ),
    DSection(
        2,
        "B",
        SECTION_ENDS[2] - 0.6,
        CutParent.TIP_DETAIL,
        0.0210,
        (0.393, 0.165),
        (3, 1),
    ),
    DSection(
        3,
        "C",
        SECTION_ENDS[3] - 0.8,
        CutParent.TIP_DETAIL,
        0.0210,
        (0.305, 0.100),
        (5, 1),
    ),
    DSection(
        4,
        "D",
        TIP_DETAIL_STATION_MM + 8.0,
        CutParent.TIP_DETAIL,
        0.0155,
        (0.3846, 0.100),
        (20, 1),
    ),
)
# Each across-flat's text, centred over its section.
D_SECTION_KEEP = {
    f"Sec{section.land}AF": (section.centre[0], section.centre[1] + 0.017)
    for section in D_SECTIONS
}
# The terminal flat's two long torque corners stay sharp in the model; their
# break limit is a drawing requirement, printed above the terminal
# across-flat.  One line: SolidWorks stores an above callout's line break but
# prints none of it (run 20261010T071427837Z: the two-line
# "TORQUE CORNERS:\nSTONE BURR ONLY" was in COM, not in the PDF; the layout
# audit found it text-unmatched, as main's pd_transgear drawings found).
# Stoning is named because it matches the number.
TORQUE_CORNER_CALLOUT = f"STONE CORNERS {TERMINAL_FLAT_EDGE_BREAK_MAX:.2f} MAX"
# An above callout is centred on its dimension's text, set as one run: that
# 40-character run read 110.6 mm wide in COM (Sec4AF's 0.3377..0.4483 at
# 20261010T071427837Z) and 8.7 mm above the text position (f68549253).
TORQUE_CALLOUT_CHAR_WIDTH = 0.1106243 / 40
TORQUE_CALLOUT_REACH = (len(TORQUE_CORNER_CALLOUT) * TORQUE_CALLOUT_CHAR_WIDTH / 2.0, 0.0087)
# Section C-C's native outline, (0.2597..0.3503) x (0.0682..0.1318) at
# 20261010T071427837Z, which the layout audit holds text off.
SECTION_C_OUTLINE_RIGHT = 0.3503


def _printable_above_callouts(callouts: dict[str, str]) -> dict[str, str]:
    """Refuse an above-callout SolidWorks would keep but not print.

    A line break in the above compartment is stored (``GetDisplayData`` reads
    it back) yet nothing of the callout reaches the PDF (main's
    draw_pd_transgear_thumbnut; this sheet's torque corners at
    20261010T071427837Z), while one-line above callouts print.
    """
    broken = sorted(name for name, text in callouts.items() if "\n" in text)
    if broken:
        raise RuntimeError(f"above-callouts with a line break do not print: {broken}")
    return callouts


# A native "SECTION A-A / SCALE 2 : 1" caption measured 45.4 x 17.0 mm (leaf
# for c8b0aad); each is hung SECTION_CAPTION_GAP under its section's ink.
SECTION_CAPTION_SIZE = (0.046, 0.017)
SECTION_CAPTION_GAP = 0.003
# The detail's caption stands this far right of its rightmost ink, B's letters.
DETAIL_CAPTION_GAP = 0.004
# A caption lands within this of its target (its anchor is not its box).  A
# note's extent reads on a grid that differs by session: on two seats (leaves
# 20260930T011635Z-1-c8539f7a, 20260930T011941Z-1-30339b73) C-C's caption top
# settled 0.30 mm under the target and D-D's 0.31 mm over the same y, both to
# the micron on both seats, so 0.3 mm was half a step and refused D-D.  At
# 0.6 mm the caption still stands 2.4 mm or more under its face.
# The layout proof measures the placed box, so the slack costs no clearance.
CAPTION_SETTLE_M = 0.0006
# The section's centre mark keeps only its cross, arms this long on the sheet:
# the template's mark scales with the view, so at 10:1 its arms and extended
# lines ran 104 mm, over the AF text, the right border and the title block.
CENTRE_MARK_ARM = 0.003
# swAnnotationType_e.swCenterMarkSym
_CENTER_MARK_ANNOTATION = 13
# An arrowhead's half-width across its shaft (the audit's 12.1 x 3.4 mm head).
SECTION_ARROW_HALF_WIDTH = 0.0017
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
    partial = section.parent in PARTIAL_CUT_PARENTS
    if bool(cut.GetPartialSection()) != partial:
        raise RuntimeError(
            f"section {section.label} is {'not ' if partial else ''}a partial "
            f"section, cut from the {section.parent.value}"
        )


class CaptionAnchor(Enum):
    """The point of a caption's box laid on its target."""

    TOP_CENTRE = "top centre"
    LEFT_MIDDLE = "left middle"


class PlacedSection(NamedTuple):
    """A built D section and the ink its layout proof measures."""

    section: DSection
    view: Any
    face: Box
    across_flat: Any
    caption: Box
    centre_marks: dict[str, Box]


def _axis_sign(adapter: Any, side: Any) -> int:
    """+1 when stations run along model +Z, -1 along -Z, read off the side view.

    A station is measured from the front face (the big end, sheet x
    BIG_END_X) toward the tip, leftward on the sheet.  The part owns the sign
    of its axis (``_end_circle`` matches |z|), so it is measured here, and a
    front face projecting anywhere but the big end fails before a cut is drawn
    on a wrong station."""
    front, along = model_points_in_view(
        adapter,
        side,
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.001)),
        label="shaft axis direction",
        names=("front face", "1 mm along +Z"),
    )
    step = along[0] - front[0]
    if (
        abs(front[0] - BIG_END_X) > 5e-4
        or abs(front[1] - SIDE_CENTER[1]) > 5e-4
        or abs(abs(step) - 0.001 * SIDE_SCALE[0] / SIDE_SCALE[1]) > 1e-6
        or abs(along[1] - front[1]) > 1e-6
    ):
        raise RuntimeError(
            f"the side view does not run the axis along sheet x from the big end: "
            f"front face {front}, 1 mm along +Z {along}"
        )
    return 1 if step < 0 else -1


def _station_point(
    station_mm: float, offset: float, sign: int
) -> tuple[float, float, float]:
    """The model point ``offset`` metres off the axis, in the side view's
    plane (model Y), at ``station_mm`` from the front face."""
    return (0.0, offset, sign * station_mm / 1000.0)


def _sheet_segment_in_parent_sketch(
    adapter: Any, parent: Any, sheet_points: Sequence[tuple[float, float]]
) -> list[tuple[float, ...]]:
    """Sheet points through the parent sketch's transform, as
    ``create_section_view`` maps its cutting line."""
    sketch = _early_bound(_early_bound(parent, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet_points:
        point = _early_bound(
            utility.CreatePoint(double_array([float(x), float(y), 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    return points


# With no outline printed, the detail's outline is the clipped shaft, not the
# circle's box: the Ø6.35 end is clipped 2.3 mm short of the circle at 4:1, so
# the axis point stands up to this far off the outline's centre along the axis.
TIP_DETAIL_CLIP_SLACK = 0.003


@_telemetry.traced("drawing.tip_detail")
def _create_tip_detail(adapter: Any, side: Any, sign: int) -> Any:
    """DETAIL E, the stepped tip at TIP_DETAIL_SCALE: the parent of B, C and D.

    The circle is sketched on the side view; its rim point lies off the axis
    in model Y, since the side view looks along model X.  A fresh detail's
    Position and ModelToViewTransform lag its ink (draw_cone_swing_platform,
    leaf 20260928T075849Z-1-882b4704), so the view is placed by its outline,
    and its projection must catch up before any cut is projected through it.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, side)):
        raise RuntimeError("failed to activate the tip detail's parent view")
    draw.ClearSelection2(True)
    centre = _station_point(TIP_DETAIL_STATION_MM, 0.0, sign)
    rim = _station_point(TIP_DETAIL_STATION_MM, TIP_DETAIL_RADIUS, sign)
    sheet = model_points_in_view(
        adapter, side, (centre, rim), label="tip detail circle", names=("centre", "rim")
    )
    points = _sheet_segment_in_parent_sketch(adapter, side, sheet)
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError("failed to sketch the tip detail circle")
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection_manager.CreateSelectData()
    selection_data.View = side
    selectable = _sw_type_info.early_bound_or_flag(circle, "ISketchSegment", "Select4")
    if not selectable.Select4(False, selection_data):
        raise RuntimeError("failed to select the tip detail circle")
    detail = ddoc.CreateDetailViewAt4(
        *TIP_DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        float(TIP_DETAIL_SCALE[0]),
        float(TIP_DETAIL_SCALE[1]),
        TIP_DETAIL_LABEL,
        1,  # swDetCircleCIRCLE
        False,  # FullOutline
        False,  # JaggedOutline
        True,  # NoOutline
        5,
    )
    draw.ClearSelection2(True)
    if detail is None:
        raise RuntimeError("CreateDetailViewAt4 returned no tip detail")
    detail = _sw_type_info.early_bound_or_flag(
        detail, "IView", "SetViewPosition", "Position"
    )
    rebuild_drawing(adapter, label="create tip detail")
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    if not math.isclose(ratio[0] / ratio[1], TIP_DETAIL_SCALE[0] / TIP_DETAIL_SCALE[1]):
        raise RuntimeError(f"tip detail scale is {ratio}, not {TIP_DETAIL_SCALE}")
    for attempt in range(4):
        outline = tuple(float(value) for value in detail.GetOutline())
        landed = ((outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0)
        anchor = tuple(float(value) for value in detail.Position)
        _telemetry.info(f"tip detail pass {attempt}: anchor={anchor} outline={outline}")
        if math.dist(landed, TIP_DETAIL_CENTER) < PLACE_SETTLE_M:
            break
        moved = [
            anchor[axis] + TIP_DETAIL_CENTER[axis] - landed[axis] for axis in range(2)
        ]
        if not detail.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to position the tip detail")
        rebuild_drawing(adapter, label="place tip detail")
    else:
        raise RuntimeError(
            f"tip detail outline centre stayed at {landed}, requested {TIP_DETAIL_CENTER}"
        )
    for attempt in range(3):
        (projected,) = model_points_in_view(
            adapter, detail, (centre,), label=f"tip detail centre, read {attempt}"
        )
        if (
            abs(projected[0] - landed[0]) <= TIP_DETAIL_CLIP_SLACK
            and abs(projected[1] - landed[1]) <= 0.0005
        ):
            break
        rebuild_drawing(adapter, label="settle tip detail")
    else:
        raise RuntimeError(
            f"tip detail projects its centre to {projected} while its outline is "
            f"centred on {landed}"
        )
    _telemetry.info(
        f"tip detail: parent circle centre {sheet[0]}, detail centre {projected}, "
        f"outline {tuple(float(value) for value in detail.GetOutline())}"
    )
    return detail


def _place_detail_letter(adapter: Any, side: Any) -> None:
    """Stand the side view's circle letter where TIP_DETAIL_LETTER_XY says."""
    circles = tuple(_read_member(_early_bound(side, "IView"), "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(
            f"expected one detail circle on the side view, found {len(circles)}"
        )
    circle = _early_bound(circles[0], "IDetailCircle")
    circle.SetLabelPosition(*TIP_DETAIL_LETTER_XY)
    rebuild_drawing(adapter, label="place tip detail letter")
    actual = tuple(float(value) for value in circle.GetLabelPosition())
    if len(actual) != 2 or math.dist(actual, TIP_DETAIL_LETTER_XY) > 1e-8:
        raise RuntimeError(f"tip detail letter position did not persist: {actual}")


def _note_box(note: Any) -> Box:
    extent = tuple(float(value) for value in note.GetExtent())
    return (extent[0], extent[1], extent[3], extent[4])


def _caption_anchor(box: Box, anchor: CaptionAnchor) -> tuple[float, float]:
    if anchor is CaptionAnchor.TOP_CENTRE:
        return ((box[0] + box[2]) / 2.0, box[3])
    return (box[0], (box[1] + box[3]) / 2.0)


def _place_view_caption(
    adapter: Any,
    view: Any,
    target: tuple[float, float],
    anchor: CaptionAnchor,
    *,
    label: str,
) -> Box:
    """Move a view's native caption so its box's ``anchor`` lands on
    ``target``, its linked fields intact, and return the measured box.

    The caption's position is not its box, so the move is measured
    (``INote.GetExtent``), as draw_cone_swing_platform places its labels.
    The sheet scale is pinned first; finalization re-applying it must not
    move a dynamic caption after this readback."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError(f"cannot pin sheet scale before {label} placement")
    notes = tuple(_read_member(_early_bound(view, "IView"), "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native {label}, found {len(notes)} notes")
    note = _early_bound(notes[0], "INote")
    linked = str(note.PropertyLinkedText or "")
    if not linked:
        raise RuntimeError(f"{label} carries no linked view fields")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    for _attempt in range(4):
        box = _note_box(note)
        point = _caption_anchor(box, anchor)
        error = (target[0] - point[0], target[1] - point[1])
        if max(abs(error[0]), abs(error[1])) < CAPTION_SETTLE_M:
            break
        x, y, z = (float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(x + error[0], y + error[1], z):
            raise RuntimeError(f"failed to move the {label}")
        rebuild_drawing(adapter, label=f"place {label}")
    else:
        raise RuntimeError(
            f"{label} stayed at {box}, its {anchor.value} requested at {target}"
        )
    if str(note.PropertyLinkedText or "") != linked:
        raise RuntimeError(f"{label} lost its linked view fields")
    _telemetry.info(f"{label}: {anchor.value} at {target}, box {box}")
    return box


def _annotation_ink(annotation: Any, label: str) -> Box:
    """The box of every line an annotation draws, in sheet metres."""
    data = _early_bound(
        _early_bound(annotation, "IAnnotation").GetDisplayData(), "IDisplayData"
    )
    lines = [
        tuple(float(value) for value in data.GetLineAtIndex2(index))
        for index in range(int(data.GetLineCount()))
    ]
    if not lines:
        raise RuntimeError(f"{label} draws no line")
    xs = [value for line in lines for value in (line[4], line[7])]
    ys = [value for line in lines for value in (line[5], line[8])]
    return (min(xs), min(ys), max(xs), max(ys))


def _trim_centre_mark(adapter: Any, view: Any, section: DSection) -> dict[str, Box]:
    """Keep the section's centre mark, if SolidWorks gave it one, as a small
    cross, and return its ink by name.

    A full section gets a mark; a partial one (cut from the tip detail) gets
    none (leaf 20260929T212711Z-1-75518df7).  The mark's size is model
    length (its 2.5 mm arms read 5 mm at 2:1 and 25 mm at 10:1), so the arm
    is divided by the section's scale."""
    label = f"section {section.label} centre mark"
    marks = tuple(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if not marks:
        _telemetry.info(f"{label}: none drawn")
        return {}
    if len(marks) != 1:
        raise RuntimeError(f"expected at most one {label}, found {len(marks)}")
    annotation = _early_bound(marks[0], "IAnnotation")
    mark = _early_bound(annotation.GetSpecificAnnotation(), "ICenterMark")
    mark.UseDocDisplaySettings = False
    mark.ShowLines = False
    mark.Size = CENTRE_MARK_ARM * section.scale[1] / section.scale[0]
    rebuild_drawing(adapter, label=f"trim {label}")
    if bool(mark.UseDocDisplaySettings) or bool(mark.ShowLines):
        raise RuntimeError(f"{label} kept its document display or its extended lines")
    ink = _annotation_ink(annotation, label)
    arm = max(ink[2] - ink[0], ink[3] - ink[1]) / 2.0
    if not 0.5 * CENTRE_MARK_ARM <= arm <= 1.5 * CENTRE_MARK_ARM:
        raise RuntimeError(
            f"{label} arms read {arm:.4f} m (size {float(mark.Size):.5f}), not "
            f"{CENTRE_MARK_ARM:.4f}: ink {ink}"
        )
    return {label: ink}


def _cut_endpoints(
    adapter: Any, parent: Any, section: DSection, sign: int
) -> tuple[tuple[float, float], tuple[float, float]]:
    """The cutting line's sheet endpoints on its parent, bottom first: drawn
    upward, the arrows look toward the big end, as every D section does."""
    scale = CUT_PARENT_SCALE[section.parent]
    offset = section.reach * scale[1] / scale[0]
    first, second = model_points_in_view(
        adapter,
        parent,
        (
            _station_point(section.station_mm, -offset, sign),
            _station_point(section.station_mm, offset, sign),
        ),
        label=f"section {section.label} cutting line",
        names=("one end", "other end"),
    )
    return (first, second) if first[1] < second[1] else (second, first)


@_telemetry.traced("drawing.d_sections")
def _add_d_sections(
    adapter: Any, parents: Mapping[CutParent, Any], sign: int
) -> list[PlacedSection]:
    """Cut each flatted land across and print its across-flat in the section,
    its centre mark a cross and its caption hung under it.

    ``curate_view_dimensions`` fails the build if a section's across-flat
    does not arrive, so every D on the sheet carries its size."""
    placed = []
    for section in D_SECTIONS:
        start, end = _cut_endpoints(adapter, parents[section.parent], section, sign)
        view = create_section_view(
            adapter,
            parents[section.parent],
            line_start=start,
            line_end=end,
            view_xy=section.centre,
            section_label=section.label,
            scale=section.scale,
            partial=section.parent in PARTIAL_CUT_PARENTS,
            label=f"land {section.land} D section",
        )
        _prepare_d_section(adapter, view, section)
        name = f"Sec{section.land}AF"
        keep = {name: D_SECTION_KEEP[name]}
        dimensions = curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=f"section {section.label}",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        by_name = {dimension_name(adapter, dimension): dimension for dimension in dimensions}
        across_flat = by_name[name]
        centre_marks = _trim_centre_mark(adapter, view, section)
        face = _section_face(adapter, view, section, sign)
        caption = _place_view_caption(
            adapter,
            view,
            (section.centre[0], face[1] - SECTION_CAPTION_GAP),
            CaptionAnchor.TOP_CENTRE,
            label=f"section {section.label} caption",
        )
        if section.land == max(FLAT_LANDS):
            # The terminal flat's torque corners stay sharp in the model; the
            # break limit rides above that flat's own across-flat value.
            set_dimension_callouts(
                adapter,
                [across_flat],
                _printable_above_callouts({name: TORQUE_CORNER_CALLOUT}),
                location="above",
            )
        placed.append(PlacedSection(section, view, face, across_flat, caption, centre_marks))
    return placed


def _section_face(adapter: Any, view: Any, section: DSection, sign: int) -> Box:
    """The D's cut face on its section, boxed round the land's full circle.

    A section's outline is no measure of its ink: SolidWorks boxes the whole
    part's depth (the Ø15.9 collar) and the cutting line's length, plus 5.6
    mm (leaf 20260929T212933Z-1-e35ef0ba: B-B's outline ran 29 mm either side
    of its 9.5 mm face, past the right border).  The face is centred on the
    axis, which must stand where the layout put the section."""
    (centre,) = model_points_in_view(
        adapter,
        view,
        (_station_point(section.station_mm, 0.0, sign),),
        label=f"section {section.label} axis",
    )
    if math.dist(centre, section.centre) > 0.001:
        raise RuntimeError(
            f"section {section.label} centres its face at {centre}, not {section.centre}"
        )
    half = SECTION_DIAS[section.land] / 2000.0 * section.scale[0] / section.scale[1]
    return (centre[0] - half, centre[1] - half, centre[0] + half, centre[1] + half)


def _section_line_ink(view: Any) -> dict[str, dict[str, Box]]:
    """Each cutting line a view carries: its two arrows and two letters as
    boxes, by section letter.  ``GetArrowInfo`` gives each arrow's start and
    end, ``GetTextInfo`` each letter's upper-left corner, both on the sheet;
    a letter is boxed one character height square (the audit's 6.35 mm "A"
    measured 5.9 wide)."""
    ink: dict[str, dict[str, Box]] = {}
    for raw in _read_member(_early_bound(view, "IView"), "GetSectionLines") or ():
        cut = _early_bound(raw, "IDrSection")
        name = str(cut.GetLabel())
        height = float(_early_bound(cut.GetTextFormat(), "ITextFormat").CharHeight)
        arrows = [float(value) for value in cut.GetArrowInfo() or ()]
        texts = [float(value) for value in cut.GetTextInfo() or ()]
        if len(arrows) != 12 or len(texts) != 6:
            raise RuntimeError(f"section line {name}: arrows {arrows}, letters {texts}")
        pad = SECTION_ARROW_HALF_WIDTH
        boxes: dict[str, Box] = {}
        for index, base in enumerate((0, 6), start=1):
            x0, y0, x1, y1 = (
                arrows[base],
                arrows[base + 1],
                arrows[base + 3],
                arrows[base + 4],
            )
            boxes[f"section {name} arrow {index}"] = (
                min(x0, x1) - pad,
                min(y0, y1) - pad,
                max(x0, x1) + pad,
                max(y0, y1) + pad,
            )
        for index, base in enumerate((0, 3), start=1):
            x, y = texts[base], texts[base + 1]
            boxes[f"section {name} letter {index}"] = (x, y - height, x + height, y)
        _telemetry.info(f"section line {name} ink: {boxes}")
        ink[name] = boxes
    return ink


def _union(boxes: Iterable[Box]) -> Box:
    boxes = list(boxes)
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _view_outline(view: Any) -> Box:
    return tuple(float(value) for value in _early_bound(view, "IView").GetOutline())


def _land_boxes(adapter: Any, view: Any, sign: int, *, label: str) -> dict[str, Box]:
    """Each flatted land's silhouette on ``view``, clipped to its outline."""
    outline = _view_outline(view)
    starts = (COLLAR_END_STATION, *SECTION_ENDS[1:-1])
    boxes = {}
    for land, start in zip(FLAT_LANDS, starts):
        radius = SECTION_DIAS[land] / 2000.0
        corners = model_points_in_view(
            adapter,
            view,
            (
                _station_point(start, -radius, sign),
                _station_point(SECTION_ENDS[land], radius, sign),
            ),
            label=f"{label} land {land}",
        )
        box = (
            max(min(x for x, _ in corners), outline[0]),
            max(min(y for _, y in corners), outline[1]),
            min(max(x for x, _ in corners), outline[2]),
            min(max(y for _, y in corners), outline[3]),
        )
        if box[0] < box[2] and box[1] < box[3]:
            boxes[f"{label} land {land}"] = box
    return boxes


def _require_apart(groups: Mapping[str, Mapping[str, Box]]) -> None:
    """Every box of each group clear of every box of every other group."""
    names = list(groups)
    for index, name in enumerate(names):
        others = {
            box_name: box
            for other in names[index + 1 :]
            for box_name, box in groups[other].items()
        }
        for box_name, box in groups[name].items():
            require_clear(box_name, box, others)


@_telemetry.traced("drawing.section_layout_proof")
def _prove_section_layout(
    adapter: Any,
    *,
    side: Any,
    detail: Any,
    iso: Any,
    sections: Sequence[PlacedSection],
    detail_caption: Box,
    dimensions: Mapping[str, Any],
    sign: int,
) -> None:
    """Prove from measured ink what the codex review of #1128 found broken:
    every section, caption, cutting line, the detail and the pictorial inside
    the frame and off the title block; the cutting lines' arrows and letters
    clear of each other, of every dimension text and of the lands; and each
    section's caption, centre mark and across-flat clear of its neighbours."""
    region = sheet_region(adapter)
    template = DRAWING_TEMPLATES[SPEC.layout]
    keep_out = {
        "title block": (
            template.title_block_left_m,
            0.0,
            template.width_m,
            template.title_block_top_m,
        )
    }
    texts = {
        name: _dimension_text_box(annotation, name)
        for name, annotation in dimensions.items()
    }
    side_lines = _section_line_ink(side)
    detail_lines = _section_line_ink(detail)
    expected = {
        CutParent.SIDE: sorted(
            s.label for s in D_SECTIONS if s.parent is CutParent.SIDE
        ),
        CutParent.TIP_DETAIL: sorted(
            s.label for s in D_SECTIONS if s.parent is CutParent.TIP_DETAIL
        ),
    }
    if (
        sorted(side_lines) != expected[CutParent.SIDE]
        or sorted(detail_lines) != expected[CutParent.TIP_DETAIL]
    ):
        raise RuntimeError(
            f"cutting lines: side view {sorted(side_lines)}, tip detail "
            f"{sorted(detail_lines)}; expected {expected}"
        )
    groups: dict[str, dict[str, Box]] = {}
    for placed in sections:
        label = f"section {placed.section.label}"
        cell = {
            f"{label} face": placed.face,
            f"{label} across-flat": _dimension_text_box(
                placed.across_flat, f"{label} across-flat"
            ),
            f"{label} caption": placed.caption,
            **placed.centre_marks,
        }
        require_clear(
            f"{label} caption",
            placed.caption,
            {name: box for name, box in cell.items() if name != f"{label} caption"},
        )
        for name, box in placed.centre_marks.items():
            require_clear(
                name,
                box,
                {f"{label} across-flat": cell[f"{label} across-flat"]},
            )
        groups[label] = {label: _union(cell.values())}
    lands = {
        **_land_boxes(adapter, side, sign, label="side view"),
        **_land_boxes(adapter, detail, sign, label="tip detail"),
    }
    for name, boxes in (*side_lines.items(), *detail_lines.items()):
        for box_name, box in boxes.items():
            if "letter" in box_name:
                require_clear(box_name, box, lands)
        groups[f"cutting line {name}"] = boxes
    groups["tip detail"] = {
        "tip detail": _view_outline(detail),
        "tip detail caption": detail_caption,
    }
    groups["isometric"] = {"isometric": _view_outline(iso)}
    groups["side view dimension texts"] = texts
    for group in groups.values():
        for name, box in group.items():
            require_inside(name, box, region)
            require_clear(name, box, keep_out)
    # A cutting line crosses its own parent's outline by design; everything
    # else keeps apart.
    apart = {name: group for name, group in groups.items() if name != "tip detail"}
    _require_apart(apart)
    for name, group in groups.items():
        if name.startswith("cutting line") or name == "tip detail":
            continue
        for box_name, box in group.items():
            require_clear(box_name, box, groups["tip detail"])
    require_clear(
        "tip detail caption",
        detail_caption,
        {name: box for boxes in detail_lines.values() for name, box in boxes.items()},
    )
    _telemetry.success(
        f"section layout proved: {len(sections)} sections, "
        f"{len(side_lines) + len(detail_lines)} cutting lines, {len(texts)} dimension texts"
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
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
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
    sign = _axis_sign(adapter, side)
    detail = _create_tip_detail(adapter, side, sign)
    _place_detail_letter(adapter, side)
    sections = _add_d_sections(
        adapter, {CutParent.SIDE: side, CutParent.TIP_DETAIL: detail}, sign
    )
    # The caption stands right of the detail's ink: B's letters and the
    # detail's own outline, whichever reaches further.
    detail_ink_right = max(
        _view_outline(detail)[2],
        *(
            box[2]
            for boxes in _section_line_ink(detail).values()
            for box in boxes.values()
        ),
    )
    detail_caption = _place_view_caption(
        adapter,
        detail,
        (detail_ink_right + DETAIL_CAPTION_GAP, TIP_DETAIL_CENTER[1]),
        CaptionAnchor.LEFT_MIDDLE,
        label="tip detail caption",
    )
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
    # symbol stands above the tip with its glyph LEFT of the terminal diameter
    # line and its text ABOVE that native diameter text, inside the left border
    # (x 0.012; a glyph at 0.016 poked through it, codex c4720c62); the
    # leader drops onto the tip's top flank inside the first 2 mm of the land.
    # No length extension line runs up there (they all hang from the bottom
    # flank) and no diameter line stands left of the terminal diameter's.
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
    _prove_section_layout(
        adapter,
        side=side,
        detail=detail,
        iso=iso,
        sections=sections,
        detail_caption=detail_caption,
        dimensions={**collar_neighbours, "CollarDia": collar},
        sign=sign,
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
