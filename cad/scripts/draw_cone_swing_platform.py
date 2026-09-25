r"""Create the curated machinist drawing for the cone swing platform.

The SLDPRT remains authoritative.  The plan imports the plate outline,
post-mount pattern, lock notch and corner radii; the native Hole Wizard callout
defines the pivot clearance hole; section A-A exposes the shallow pivot-head
relief and plate thickness in solid lines.  Display precision comes from the
model.

The platform is an asymmetric steel wedge with a 1/4-in close-clearance pivot
hole over the stock screw shoulder, paired 1/4-20 post-mount taps, an open
west-edge lock notch, four rounded plan corners and the counterbored slot
for the tip block's hold-down screw (I31).  The three plan views run 1:2
and pivot section A-A 2:1; the lock-notch plan also carries the slot's
station from the pivot.  Slot detail B enlarges a 12 mm radius around the
slot at 2:1, hidden lines dashed, at sheet (88, 44) mm, its cutters named
by leadered notes; section C-C (1:1), cut on the plate-profile plan, runs
along the slot for the counterbore depth.  The isometric runs 1:3.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_swing_platform.py cone-swing-platform
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_leader_note,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    check_drawing_layout,
    curate_view_dimensions,
    finalize_drawing,
    rebuild_drawing,
    new_project_drawing,
    model_point_in_view,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_dimension_callouts,
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
import build_cone_swing_platform as _part
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)
from _hole_spec import blind_cut_dia_mm
from _surface_finish import surface_finish_by_key
from cone_swing_platform_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIVOT_HOLE_DIA,
    PLATE_STOCK_CALLOUT,
    PLATE_THICKNESS,
    POST_MOUNT_SPEC,
    SURFACE_FINISHES,
    TIP_CBORE_W,
    TIP_SCREW_HALF_TRAVEL,
    TIP_SCREW_LOCAL_Z,
    TIP_SLOT_W,
)
from diagnostics.drawing_layout_audit import collect_document, describe_sheet


SPEC = DRAWINGS_BY_NAME["cone_swing_platform"]
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

SHEET_SCALE = (1.0, 2.0)  # title block states the principal (plan) scale; iso and section carry their own

# Sheet layout (meters).  Three 1:2 plan views separate the profile, hole
# pattern and lock-notch definitions instead of routing unrelated leaders
# through one narrow 224-mm wedge.  The section and pictorial occupy the
# right-hand field.
PROFILE_CENTER = (0.075, 0.190)
FEATURE_CENTER = (0.180, 0.190)
NOTCH_CENTER = (0.260, 0.190)
ISO_CENTER = (0.355, 0.205)
# The section group sits up and right in the open field below the isometric,
# clear of the lock-notch caption; every section annotation shares this shift.
# x 0.030, not 0.020: at 0.020 section C-C's 2.80 arrow line ran up through
# the "(6.35)" stock text left of A-A (aa9766da).  The group's right-hand ink
# then ends ~410 mm, inside the 419 mm border.
SECTION_SHIFT = (0.030, 0.015)


def _shifted(x: float, y: float) -> tuple[float, float]:
    return (x + SECTION_SHIFT[0], y + SECTION_SHIFT[1])


SECTION_CENTER = _shifted(0.335, 0.105)
# The layout audit boxes an Ra symbol 39 mm right of its anchor, so the
# base-slide finish keeps its aa9766da sheet x (box to 0.414) rather than
# taking SECTION_SHIFT's extra 10 mm past the border (0.4189).
BASE_SLIDE_FINISH_XY = (0.375, _shifted(0.355, 0.120)[1])

PROFILE_KEEP = {
    "PlateLenDim": (0.025, PROFILE_CENTER[1]),
    "NorthEastX": (0.045, 0.105),
    "NorthWestX": (0.100, 0.115),
    "SouthWestX": (0.104, 0.258),
    "SouthEastX": (0.045, 0.259),
    # Radial rays must meet actual trimmed corners, not circle extensions.
    # CornerNE/R10 is left and CornerNW/R8 is right in this view.  R10 and
    # R12 shelves sit just above horizontal enough to land inside their arcs
    # while clearing the 223.4 witness lines.
    "CornerNER": (0.045, 0.139),
    "CornerNWR": (0.135, 0.118),
    "CornerSWR": (0.110, 0.249),
    "CornerSER": (0.040, 0.2435),
}
FEATURE_KEEP = {
    # Short lines (12 characters, ~34 mm at most) between the 195.09 line
    # (x 0.130) and the plate's west edge (x 0.1679): on three the 50 mm
    # "OPEN TO NORTH EDGE" ran through both (8783776d).  The block stands on
    # its shelf (y 0.1438) and grows up, 5.6 mm a line, under the 13.12 row.
    "PivotBearingReliefDia": (0.1490, 0.155),
    "PostMountWestX": (0.150, 0.185),
    "PostMountWestZ": (0.225, 0.175),
    "PostMountEastX": (0.205, 0.185),
    "PostMountEastZ": (0.130, 0.175),
}
# Named by features on the sheet, not a compass: to a blind reader of
# 68565ace "OPEN TO NORTH EDGE" contradicted a relief opening toward the
# sheet's lower edge, since sheet-down is model north (codex blocker B2; B3's
# phantom 0.695 lip followed from it).
RELIEF_WIDTH_CALLOUT = "TOP RELIEF\nCTR ON PIVOT\nOPEN THRU\nPIVOT END"
# The three 1:2 plans centre on the plate's plan box; sheet +x is model +x
# (west), sheet +y model -z (south).
PLAN_SCALE = 0.0005
_PLAN_MID_X = (_part.WEST_HALF_S - _part.EAST_HALF_S) / 2.0
_PLAN_MID_Z = _part.NORTH_OVERHANG - _part.PLATE_LEN / 2.0


def plan_xy(center: tuple[float, float], x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of plate-local (x, z) on the 1:2 plan centred at ``center``."""
    return (
        center[0] + (x_mm - _PLAN_MID_X) * PLAN_SCALE,
        center[1] - (z_mm - _PLAN_MID_Z) * PLAN_SCALE,
    )


def _plan_east_edge_x(z_mm: float) -> float:
    run = (_part.NORTH_OVERHANG - z_mm) / _part.PLATE_LEN
    return -(_part.HALF_WIDTH_N + (_part.EAST_HALF_S - _part.HALF_WIDTH_N) * run)


# I31 moved the tip slot 27.7 south of the pivot, out of reach of one detail
# circle, so its station prints here: on the plan's open east side, sharing
# nothing with the NorthEdgeZ/CapECz witnesses on the west.  The dimension
# line stands 9 mm (sheet) off the plate's east edge at the slot; its text
# hangs left of it, just south of the span (outside it, so the line does not
# run through the value).
_NOTCH_SLOT_XY = plan_xy(NOTCH_CENTER, -TIP_SCREW_HALF_TRAVEL, TIP_SCREW_LOCAL_Z)
TIP_SLOT_Z_LINE_X = plan_xy(NOTCH_CENTER, _plan_east_edge_x(TIP_SCREW_LOCAL_Z), 0.0)[0] - 0.009
NOTCH_KEEP = {
    # Pivot-to-north-edge lives here, sharing the 205.81 pivot witness: in the
    # profile the R8 corner ray has no path that clears this dimension.
    "NorthEdgeZ": (0.270, 0.150),
    # Text between its witnesses: outside, it read as spanning from the corner.
    "CapECx": (0.2652, 0.258),
    "CapECz": (0.305, 0.180),
    "CapEDia": (0.285, 0.259),
    # The run angle (PR #830, Codex P1: without it the rails had no
    # direction).  Its vertex is the north rail's closed-end corner, sheet
    # ~(0.2730, 0.2386) with the pivot at (0.2568, 0.1377); the text sits on
    # the bisector 24 mm out, inside the 9.11 deg wedge -- a text point
    # outside it selects the supplement or the opposite sector (d22701cf8's
    # sheet-spanning arc).  A ~11.8 x 3.8 mm "9.11°" box there keeps ~2.0 mm
    # under the 205.81 cap-centre witness (y 0.2406) and ~2.2 mm left of that
    # dimension's line (x 0.305).  Laid out from those figures, NOT from a
    # render; _assert_notch_angle_in_wedge proves the sector on the sheet.
    "NotchRunAngle": (0.2969, 0.2367),
    "TipSlotZ": (TIP_SLOT_Z_LINE_X, _NOTCH_SLOT_XY[1] + 0.004),
}
SECTION_KEEP = {
    # Outside its witnesses, the text hangs LEFT of the dimension line (away
    # from the plate), right edge on the line and centred on this y.  The
    # three lines (~26 x 15.3 mm) sit in x 0.3035..0.3295, y 0.1213..0.1366:
    # under the 205.81 witness (0.1379), right of C-C's 2.80 arrow line
    # (x 0.2993).  The flush widest line sits above the top witness, the
    # set-back last line beside the arrowhead (aa9766da: "AS SUPPLIED" there
    # ran its D into it).
    "PlateThk": _shifted(0.300, 0.114),
    "PivotBearingReliefDepth": _shifted(0.365, 0.115),
}

# I31 tip-block hold-down slot: too small to dimension at 1:2, so DETAIL B
# enlarges the slot on the hole-location plan to 2:1, with
# hidden lines shown so the underside counterbored slot reads dashed.  At
# 1:1 (run 7959e994) five dimensions and two cutter callouts crowded a 24 mm
# circle, texts over the outline and each other; 2:1 gives them the room.
# The counterbore depth is section C-C's imported dimension.
#
# The free band is x 0.0127..0.216 under the plan captions (y <= 0.0805)
# and above the bottom border (y >= 0.0127).  Run e86bf319 put the detail in
# its right half, where the title block (x >= 0.216, y <= 0.066) boxed its
# callouts in and its native label fell 8.9 mm through the bottom border.
# So the relief-fit note moves to the band's lower right and the detail to
# its left half: the wide callouts get the open field right of the circle.
# A vertical dimension's text hangs outward from its dimension line (the
# e86bf319 extents: left of a left-side line, right of a right-side one).
# Sheet +x is model +x (west) and sheet +y is model -z (south) in these plans.
# I31: centred on the slot.  Until then the circle took in the pivot as
# well; 27.7 south, the slot's station from it prints on the notch plan.
DETAIL_MODEL_Z = TIP_SCREW_LOCAL_Z
DETAIL_RADIUS_MM = 12.0
DETAIL_SCALE = (2, 1)
_DETAIL_S = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
# The layout audit boxes a detail view by its native outline, which run
# eaafbc73 measured at the circle plus 10.4 mm a side ([53.6, 9.6]..
# [122.4, 78.4] mm around a 48 mm circle): it crossed the 9.7 mm zone border
# by 0.1 and ran 3.5 into the relief note.  Centred here, the outline sits
# at [49.1, 10.6]..[117.9, 79.4]: right of the label, under the plan
# captions (80.5) and 2.1 short of the note.
DETAIL_CENTER = (0.0835, 0.045)
DETAIL_OUTLINE_PAD = 0.0104
DETAIL_SHEET_RADIUS = DETAIL_RADIUS_MM * _DETAIL_S
_SLOT_Y = DETAIL_CENTER[1] + (DETAIL_MODEL_Z - TIP_SCREW_LOCAL_Z) * _DETAIL_S
# Between its extension lines a vertical dimension's text is CENTRED on its
# dimension line, which then runs through it (81788ce9: "SLOT|THRU",
# "11.|00"); outside them the text hangs outward, one edge on the line,
# centred on the keep y.  So every vertical dimension here parks its text
# OUTSIDE its span.  The two width spans overlap (counterbore 38.7..51.3,
# slot 41..49), so the slot's dimension line runs up past the
# counterbore's upper extension line to its text (below the spans the
# detail's own label sits, since I31 centred the circle on the slot).  The slot sits nearest
# the part, the counterbore outboard (its extension lines then never cross
# the slot's dimension line inside the slot's span).  The cutters are named
# by leadered notes, not dimension text.
DETAIL_KEEP = {
    # Above the circle, each 2.00 outside its own extension lines and under
    # the plan caption row (y >= 0.0805).  The west one sits in toward the
    # circle, left of the through-slot leader's path.
    "TipSlotEastCx": (
        DETAIL_CENTER[0] - 0.020,
        DETAIL_CENTER[1] + DETAIL_SHEET_RADIUS + 0.005,
    ),
    "TipSlotWestCx": (
        DETAIL_CENTER[0] + 0.0135,
        DETAIL_CENTER[1] + DETAIL_SHEET_RADIUS + 0.005,
    ),
    # Left, nearest the circle: the through slot, text above both spans
    # (over the counterbore's upper extension line).
    "TipSlotW": (DETAIL_CENTER[0] - 0.0275, _SLOT_Y + 0.0125),
    # Left, outboard: the counterbored slot, text above the slot's.
    "TipCboreW": (DETAIL_CENTER[0] - 0.0465, _SLOT_Y + 0.0225),
}
# Arrowheads inside the extension lines: outside, the slot's 8 mm span put
# an arrow tail across the counterbore's upper extension line (81788ce9).
DETAIL_ARROWS_INSIDE = ("TipSlotW", "TipCboreW")
# The cutter that sets each +0.10/0 width band, named by a leadered note
# (2.5 mm text, anchored upper-left) in the open field right of the circle.
# Each leader tip lands on the WEST (sheet-right) end arc of its slot, at a
# sheet angle from that arc's centre.  A leadered note's INote.GetExtent --
# what the layout audit boxes -- runs from its leader tip to its text, so two
# notes whose texts sit on the same side of their tips nest (ec70186e: 65.5
# x 12.1 mm overlap).  The slot note therefore rises from the arc's upper
# quadrant to text above; the counterbore note drops from its lower quadrant
# to text below, its leader crossing pivot-to-slot's dimension line (the only
# path: below that line's foot sits the relief note).
_WEST_ARC_CENTER = (DETAIL_CENTER[0] + 2.0 * _DETAIL_S, _SLOT_Y)


@dataclass(frozen=True)
class CutterNote:
    """One leadered cutter note: ``text`` at ``text_xy`` pointing at an arc."""

    key: str
    text: str
    text_xy: tuple[float, float]
    feature: str  # the native cut whose end arc the leader names
    radius_mm: float
    tip_deg: float  # sheet angle of the tip on the west end arc
    model_y_mm: float | None  # the arc's face; None = either coincident arc


CUTTER_NOTES = (
    CutterNote(
        "slot",
        f"<MOD-DIAM>{TIP_SLOT_W:g} END MILL SLOT THRU",
        (0.121, 0.0785),
        "TipScrewSlot",
        TIP_SLOT_W / 2.0,
        60.0,
        PLATE_THICKNESS,  # the visible top-face arc, not the hidden floor one
    ),
    CutterNote(
        "cbore",
        f"<MOD-DIAM>{TIP_CBORE_W:g} END MILL C'BORE SLOT\nFROM UNDERSIDE",
        # I31: 2.5 mm lower than 0.047, so its extent stays 3 mm under the
        # slot note's, whose tip came down 10 mm with the re-centred slot.
        (0.121, 0.0445),
        "TipScrewCbore",
        TIP_CBORE_W / 2.0,
        -35.0,
        None,  # the dashed arc: underside outline and floor edge project as one
    ),
)
CUTTER_NOTE_CHAR_HEIGHT = 0.0025
# Physical-edge bound on a leader tip, model metres (the R8 proof's bound).
LEADER_TIP_BOUND_M = 0.00001


def cutter_note_tip(note: CutterNote) -> tuple[float, float]:
    """The sheet point on ``note``'s west end arc its leader must touch."""
    angle = math.radians(note.tip_deg)
    r = note.radius_mm * _DETAIL_S
    return (
        _WEST_ARC_CENTER[0] + r * math.cos(angle),
        _WEST_ARC_CENTER[1] + r * math.sin(angle),
    )


def cutter_note_model_tip(note: CutterNote) -> tuple[float, float, float]:
    """``cutter_note_tip`` in part metres (sheet +x = +x, sheet +y = -z)."""
    angle = math.radians(note.tip_deg)
    return (
        (2.0 + note.radius_mm * math.cos(angle)) / 1000.0,
        (note.model_y_mm if note.model_y_mm is not None else PLATE_THICKNESS) / 1000.0,
        (TIP_SCREW_LOCAL_Z - note.radius_mm * math.sin(angle)) / 1000.0,
    )
# The native "DETAIL B / SCALE 2:1" label, moved by its measured extent:
# lower left of its box, in the band's lower-left corner under the slot text.
DETAIL_LABEL_LOWER_LEFT = (0.016, 0.015)
# The pivot relief-fit note (2.5 mm text, ~0.095 x 0.018): anchored by its
# upper-left corner, lower right of the free band, left of the title block.
RELIEF_NOTE_XY = (0.120, 0.034)
# The MHA-142 named-exception note and its tap-break override (2.5 mm text,
# two lines, ~141 x 8.8 mm), anchored upper-left in the empty band above the
# title block (0.066): right of the plan caption row (x <= 0.2185), under the
# C-C label (y >= 0.0815) and the A-A label (y >= 0.0853).  A sheet must state
# a named exception (codex review of 68565ace, blocker B1).
ENGAGEMENT_NOTE_XY = (0.222, 0.0795)
# SECTION C-C cuts across the plate along the slot, so the counterbore's
# depth is an imported model dimension (drawing-simplicity rule 2: a typed
# "4.20 DEEP" was not).  Its cutting line lives on the 1:2 plate-profile
# plan, not in detail B: in the detail it lay ON the slot centreline, so
# pivot-to-slot's extension line ran along it and its arrows sat in every
# width extension's path.  On the plan the default arrows (looking north,
# sheet-down) ran beside the NorthWestX extension line and through the R8 leader,
# so the cut looks SOUTH (arrows sheet-up).
#
# The line runs PAST both plate edges (a full section across the slot
# station): as a +-9 mm partial cut its sheet-up arrows sat inside the
# plate, and the west letter, 31..44 mm south of the cut where the plate
# flares, landed on the sloped west edge (Main's eye-pass of 8783776d).
# Each end clears its edge at the letter's far station by the letter's half
# width (5.5 model mm at 1:2) plus 1.5 -- SLOT_SECTION_LINE_X_MM, derived
# below from the plate's edges.
CC_LETTER_TOP_SHEET = 0.022  # a letter's far side above the line (8783776d)
CC_LETTER_HALF_W_MM = 5.5
CC_LETTER_EDGE_CLEAR_MM = 1.5
# 1:1, full width: the strip is the plate edge-on x 6.35, in the
# pocket right of the drill callout RD1 (x <= 0.246), under the notch plan
# (y >= 0.1286) and its lifted caption (y >= 0.1207), with its native label
# centred directly under it, right of the plan caption row (x <= 0.2185)
# and above the title block (y 0.066): 8783776d printed the label 50 mm left
# of its strip.  5 mm lower than aa9766da, to make room for the caption.
SLOT_SECTION_CENTER = (0.279, 0.1059)
# Where the depth text hangs: beyond the strip's left end, or mirrored past
# its right end when SolidWorks attaches the depth at the right-hand
# counterbore edge (looking south mirrors the strip).
SLOT_SECTION_KEEP = {
    "TipCboreDepth": (SLOT_SECTION_CENTER[0] - 0.0205, SLOT_SECTION_CENTER[1]),
}
SLOT_SECTION_DEPTH_RIGHT = (SLOT_SECTION_CENTER[0] + 0.0205, SLOT_SECTION_CENTER[1])
# The native label box measured 46.5 x 16.2 mm; centred under the strip.
SLOT_SECTION_LABEL_LOWER_LEFT = (SLOT_SECTION_CENTER[0] - 0.02325, 0.0815)
# The lock-notch caption sits directly under its own view, not on the plan
# caption row: there it printed right under "SECTION C-C / SCALE 1:1" and
# read as that section's caption (aa9766da).  Its 59.7 x 4.8 mm box,
# anchored upper-left and centred under the notch plan, clears the 7.0
# arrow tip (y 0.1276) above and the C-C strip (ink top ~0.1152) below.
NOTCH_CAPTION_UPPER_LEFT = (NOTCH_CENTER[0] - 0.02985, 0.1255)
# The pivot on the profile plan, from the NE/NW corner-radius stations below
# (their fillet centres sit at model (-6.35, -3) and (0.97, -1) mm).
PROFILE_PIVOT_XY = (0.0718, 0.1377)


def plate_edge_mm(z_mm: float, side: int) -> float:
    """Model x of the plate's straight east (-1) / west (+1) edge at ``z_mm``."""
    run = (_part.NORTH_OVERHANG - z_mm) / _part.PLATE_LEN
    if side < 0:
        return -(_part.HALF_WIDTH_N + (_part.EAST_HALF_S - _part.HALF_WIDTH_N) * run)
    return _part.WEST_HALF_N + (_part.WEST_HALF_S - _part.WEST_HALF_N) * run


_CC_LETTER_FAR_Z = TIP_SCREW_LOCAL_Z - CC_LETTER_TOP_SHEET / PLAN_SCALE
SLOT_SECTION_LINE_X_MM = tuple(
    side
    * math.ceil(
        (
            abs(plate_edge_mm(_CC_LETTER_FAR_Z, side))
            + CC_LETTER_HALF_W_MM
            + CC_LETTER_EDGE_CLEAR_MM
        )
        * 10.0
        - 1e-6
    )
    / 10.0
    for side in (-1, 1)
)


def slot_section_line_model_points() -> tuple[tuple[float, float, float], ...]:
    """The C-C cutting line's ends, part metres, past both edges at the slot."""
    return tuple(
        (x / 1000.0, PLATE_THICKNESS / 1000.0, TIP_SCREW_LOCAL_Z / 1000.0)
        for x in SLOT_SECTION_LINE_X_MM
    )




_COSMETIC_THREAD_LAYER = "COSMETIC-THREADS-HIDDEN"


def _assert_notch_angle_in_wedge(
    adapter: Any, view: Any, annotations: list[Any]
) -> None:
    """Prove the run angle's text sits in its acute 9.11 deg sector.

    An angular dimension measures the sector that holds its text, so a text
    point beside the wedge prints the supplement (170.89) or the vertically
    opposite sector's arc.  The sector is re-derived from the model through
    the placed view, not from the layout's own sheet figures.
    """
    matches = [
        item for item in annotations if dimension_name(adapter, item) == "NotchRunAngle"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one NotchRunAngle annotation, found {len(matches)}")
    annotation = _early_bound(matches[0], "IAnnotation")
    text = tuple(float(value) for value in annotation.GetPosition())
    vx, vz = _part.NOTCH_ANGLE_VERTEX_XZ
    run = math.radians(_part.NOTCH_RUN_DEG)
    y = PLATE_THICKNESS / 1000.0

    def sheet(x_mm: float, z_mm: float, label: str) -> tuple[float, float]:
        return model_point_in_view(
            adapter, view, (x_mm / 1000.0, y, z_mm / 1000.0), label=label
        )

    vertex = sheet(vx, vz, "notch angle vertex")
    ray_end = sheet(vx + 10.0, vz, "notch angle ray")
    run_end = sheet(vx + 10.0 * math.cos(run), vz + 10.0 * math.sin(run), "notch run")
    ray = (ray_end[0] - vertex[0], ray_end[1] - vertex[1])
    run_dir = (run_end[0] - vertex[0], run_end[1] - vertex[1])
    to_text = (text[0] - vertex[0], text[1] - vertex[1])

    def cross(a: tuple[float, float], b: tuple[float, float]) -> float:
        return a[0] * b[1] - a[1] * b[0]

    turn = cross(ray, run_dir)
    inside = (
        cross(ray, to_text) * turn > 0.0
        and cross(to_text, run_dir) * turn > 0.0
        and ray[0] * to_text[0] + ray[1] * to_text[1] > 0.0
    )
    _telemetry.info(
        f"NotchRunAngle text={text[:2]} vertex={vertex} ray={ray_end} "
        f"run={run_end} inside_acute_sector={inside}"
    )
    if not inside:
        raise RuntimeError(
            f"NotchRunAngle text {text[:2]} is outside its acute sector at "
            f"{vertex}; it would print the supplement or the opposite arc"
        )


def _hide_profile_cosmetic_threads(adapter: Any, view: Any) -> None:
    """Hide the redundant model cosmetic-thread callout in the profile view."""
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        if (
            int(
                manager.AddLayer(
                    _COSMETIC_THREAD_LAYER,
                    "cosmetic thread ink hidden in profile view",
                    0,
                    0,
                    0,
                )
            )
            != 1
        ):
            raise RuntimeError("failed to add hidden cosmetic-thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("cosmetic-thread layer did not remain hidden")

    hidden = 0
    hidden_callouts = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 1:  # swCosmeticThread
            continue
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError("profile cosmetic thread refused the hidden layer")
        thread = _early_bound(annotation.GetSpecificAnnotation(), "ICThread")
        raw_callout = _read_member(thread, "ThreadCallout")
        if raw_callout is not None:
            callout = _early_bound(raw_callout, "INote")
            callout_annotation = _early_bound(
                _read_member(callout, "GetAnnotation"), "IAnnotation"
            )
            callout_annotation.Layer = _COSMETIC_THREAD_LAYER
            if str(callout_annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
                raise RuntimeError("profile thread callout refused the hidden layer")
            hidden_callouts += 1
        hidden += 1
    if not hidden:
        raise RuntimeError("profile view has no cosmetic thread to hide")
    if not hidden_callouts:
        raise RuntimeError("profile cosmetic threads have no callout note to hide")
    rebuild_drawing(adapter, label="hide profile cosmetic threads")


def _position_section_label(adapter: Any, section: Any) -> None:
    """Keep the native section caption below, rather than inside, the section."""
    notes = tuple(_read_member(section, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native section label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    target = (*_shifted(0.335, 0.085), 0.0)
    if not annotation.SetPosition2(*target):
        raise RuntimeError("failed to position native section label")
    adapter.currentModel.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if max(abs(actual[i] - target[i]) for i in range(3)) > 1e-8:
        raise RuntimeError(
            f"native section label position did not persist: {actual}; "
            f"requested={target}"
        )


def _note_annotation_name(note: Any) -> str:
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    return str(annotation.GetName() or "")


def _position_view_label(
    adapter: Any,
    view: Any,
    lower_left: tuple[float, float],
    *,
    label: str,
    added_notes: Sequence[Any] = (),
) -> None:
    """Move a view's native label so its box's lower-left lands at ``lower_left``.

    The label's anchor is not its box corner, so the move is measured: read
    ``INote.GetExtent``, shift the anchor by the corner's error, read back.
    The sheet scale is pinned first; finalization re-applying it must not
    move a dynamic label after this readback.

    ``IView::GetNotes`` returns every note in the view, so notes this script
    added there (detail B's cutter notes: 498160d1 found 3) are excluded by
    their own annotation names, not by text; exactly one native label must
    remain.
    """
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError(f"cannot pin sheet scale before {label} placement")
    added = {_note_annotation_name(item) for item in added_notes}
    if "" in added or len(added) != len(added_notes):
        raise RuntimeError(f"{label}: added notes lack distinct annotation names")
    notes = tuple(_read_member(view, "GetNotes") or ())
    native = [item for item in notes if _note_annotation_name(item) not in added]
    if len(native) != 1 or len(notes) - len(native) != len(added):
        raise RuntimeError(
            f"expected one native {label} beside {len(added)} added notes, "
            f"found {len(notes)} notes ({len(native)} not added here)"
        )
    note = _early_bound(native[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    for _attempt in range(2):
        extent = tuple(float(v) for v in note.GetExtent())
        error = (lower_left[0] - extent[0], lower_left[1] - extent[1])
        if max(abs(error[0]), abs(error[1])) < 0.0002:
            break
        anchor = tuple(float(v) for v in _read_member(annotation, "GetPosition"))
        moved = (anchor[0] + error[0], anchor[1] + error[1], 0.0)
        if not annotation.SetPosition2(*moved):
            raise RuntimeError(f"failed to position native {label}")
        adapter.currentModel.EditRebuild3()
    extent = tuple(float(v) for v in note.GetExtent())
    print(f"{label}: requested lower-left={lower_left} extent={extent}")
    if max(abs(lower_left[0] - extent[0]), abs(lower_left[1] - extent[1])) > 0.0005:
        raise RuntimeError(
            f"native {label} landed at {extent[:2]}, requested {lower_left}"
        )


def _create_detail_view(
    adapter: Any,
    parent_view: Any,
    *,
    model_center_mm: tuple[float, float, float],
    radius_mm: float,
    view_xy: tuple[float, float],
    detail_label: str,
    scale: tuple[int, int],
    label: str,
) -> Any:
    """Create a circular detail view around one model point of ``parent_view``.

    The circle is sketched in the parent view's own sketch space: the model
    point is projected to the sheet, then through the sketch transform, the same
    path ``create_section_view`` uses for its cutting line.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if not ddoc.ActivateView(view_name(adapter, parent_view)):
        raise RuntimeError(f"failed to activate detail parent view ({label})")
    draw.ClearSelection2(True)
    center_m = tuple(value / 1000.0 for value in model_center_mm)
    rim_m = (center_m[0] + radius_mm / 1000.0, center_m[1], center_m[2])
    sheet = [
        model_point_in_view(adapter, parent_view, point, label=f"{label} {name}")
        for name, point in (("centre", center_m), ("rim", rim_m))
    ]
    sketch = _early_bound(_early_bound(parent_view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet:
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        circle = sketch_manager.CreateCircle(*points[0], *points[1])
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the detail circle ({label})")
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection_manager.CreateSelectData()
    selection_data.View = parent_view
    selectable = _sw_type_info.early_bound_or_flag(circle, "ISketchSegment", "Select4")
    if not selectable.Select4(False, selection_data):
        raise RuntimeError(f"failed to select the detail circle ({label})")
    detail = ddoc.CreateDetailViewAt4(
        float(view_xy[0]),
        float(view_xy[1]),
        0.0,
        0,  # swDetViewSTANDARD
        float(scale[0]),
        float(scale[1]),
        detail_label,
        1,  # swDetCircleCIRCLE
        True,  # FullOutline
        False,  # JaggedOutline
        False,  # NoOutline
        5,
    )
    draw.ClearSelection2(True)
    if detail is None:
        raise RuntimeError(f"CreateDetailViewAt4 returned no view ({label})")
    detail = _sw_type_info.early_bound_or_flag(
        detail, "IView", "SetViewPosition", "Position"
    )
    rebuild_drawing(adapter, label=f"create detail view {detail_label}")
    # A detail view's Position is its model-origin anchor, not the circle
    # centre (run 2b643c17 placed the circle 99 mm below the request).  Move
    # the anchor until the circle's model centre lands on ``view_xy``.
    for attempt in range(2):
        landed = model_point_in_view(
            adapter, detail, center_m, label=f"{label} centre, pass {attempt}"
        )
        anchor = tuple(float(v) for v in detail.Position)
        if max(abs(landed[0] - view_xy[0]), abs(landed[1] - view_xy[1])) < 0.0002:
            break
        moved = (
            anchor[0] + view_xy[0] - landed[0],
            anchor[1] + view_xy[1] - landed[1],
        )
        if not detail.SetViewPosition(double_array(list(moved)), False):
            raise RuntimeError(f"failed to position the detail view ({label})")
        rebuild_drawing(adapter, label=f"place detail view {detail_label}")
    landed = model_point_in_view(adapter, detail, center_m, label=f"{label} centre")
    print(
        f"detail {detail_label}: parent_sheet_centre={sheet[0]} "
        f"sketch_centre={points[0]} requested={view_xy} landed={landed} "
        f"outline={tuple(float(v) for v in detail.GetOutline())}"
    )
    if max(abs(landed[0] - view_xy[0]), abs(landed[1] - view_xy[1])) > 0.0005:
        raise RuntimeError(
            f"detail {detail_label} centre landed at {landed}, requested {view_xy}"
        )
    return detail


def _look_slot_section_south(
    adapter: Any, parent: Any, section: Any, cut: Any
) -> None:
    """Point section C-C's arrows sheet-up (looking south) and prove the strip.

    The view direction is read from the section's own projection, not from
    arrow-array layouts: with screen-right r and screen-up u, the sight line
    is u x r, so it runs along -z (south) exactly when model +x's sheet-x sign
    times model +y's sheet-y sign is positive.  The strip must be the full
    width of the 6.35 plate at the slot station, at 1:1 -- the geometry section C-C
    had in detail B.
    """
    z = TIP_SCREW_LOCAL_Z / 1000.0

    def x_direction() -> float:
        base = model_point_in_view(adapter, section, (0.0, 0.003, z), label="C-C origin")
        east = model_point_in_view(adapter, section, (0.001, 0.003, z), label="C-C +x")
        up = model_point_in_view(adapter, section, (0.0, 0.004, z), label="C-C +y")
        return (east[0] - base[0]) * (up[1] - base[1])

    if x_direction() < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="section C-C looks south")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section C-C cut direction did not persist")
    direction = x_direction()
    if not direction > 0.0:
        raise RuntimeError(f"section C-C still looks north (x/y sign product {direction})")
    east = plate_edge_mm(TIP_SCREW_LOCAL_Z, -1) / 1000.0
    west = plate_edge_mm(TIP_SCREW_LOCAL_Z, +1) / 1000.0
    low = model_point_in_view(
        adapter, section, (east, 0.0, z), label="C-C strip east underside"
    )
    high = model_point_in_view(
        adapter, section, (west, PLATE_THICKNESS / 1000.0, z), label="C-C strip west top"
    )
    span = (high[0] - low[0], high[1] - low[1])
    print(
        f"section C-C: reversed={bool(cut.GetReversedCutDirection())} "
        f"x_dir={direction} strip_span_m={span} "
        f"arrows={tuple(float(v) for v in (cut.GetArrowInfo() or ()))} "
        f"texts={tuple(float(v) for v in (cut.GetTextInfo() or ()))} "
        f"parent_line_info="
        f"{tuple(float(v) for v in (_early_bound(parent, 'IView').GetSectionLineInfo2() or ()))}"
    )
    expected = (west - east, PLATE_THICKNESS / 1000.0)
    if any(abs(abs(span[i]) - expected[i]) > 1e-6 for i in (0, 1)):
        raise RuntimeError(
            f"section C-C strip is {span}, expected the 1:1 {expected} full width"
        )


def _ink_segments(annotation: Any) -> list[tuple[float, float, float, float]]:
    """An annotation's straight ink runs, sheet metres (x0, y0, x1, y1).

    ``IDisplayData::GetLineAtIndex3`` ends with startPt[3], endPt[3]; the
    start index is read from the array length, as the layout audit does.
    """
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    runs = []
    for index in range(int(data.GetLineCount())):
        values = [float(v) for v in (data.GetLineAtIndex3(index) or ())]
        if len(values) < 10:
            continue
        start = len(values) - 6
        runs.append(
            (values[start], values[start + 1], values[start + 3], values[start + 4])
        )
    return runs


def _set_arrows_inside(
    adapter: Any, annotations: list[Any], names: tuple[str, ...]
) -> None:
    """Pin the named dimensions' arrowheads between their extension lines."""
    found = set()
    for item in annotations:
        name = dimension_name(adapter, item)
        if name not in names:
            continue
        display = _early_bound(item.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = 0  # swDimensionArrowsSide_e.swDimArrowsInside
        if int(display.ArrowSide) != 0:
            raise RuntimeError(f"{name} did not keep its arrows inside")
        found.add(name)
    if found != set(names):
        raise RuntimeError(f"arrows-inside dimensions missing: {set(names) - found}")
    rebuild_drawing(adapter, label="detail B arrows inside")


def _keep_depth_on_its_attached_end(adapter: Any, annotations: list[Any]) -> None:
    """Park the C-C depth text beside the strip end its extension lines leave.

    Looking south mirrors the strip; SolidWorks attaches the imported depth to
    whichever end it picks.  Text on the far side would stretch both extension
    lines across the strip, so if the ink reaches past the strip centre the
    text moves to the mirrored keep.
    """
    matches = [
        item for item in annotations if dimension_name(adapter, item) == "TipCboreDepth"
    ]
    if len(matches) != 1:
        raise RuntimeError("expected one native counterbore depth in section C-C")
    annotation = _early_bound(matches[0], "IAnnotation")
    runs = _ink_segments(annotation)
    reach = max((max(run[0], run[2]) for run in runs), default=float("-inf"))
    print(f"TipCboreDepth ink: runs={runs} max_x={reach}")
    if reach <= SLOT_SECTION_CENTER[0]:
        return
    target = (*SLOT_SECTION_DEPTH_RIGHT, 0.0)
    if not annotation.SetPosition2(*target):
        raise RuntimeError("failed to move the C-C depth text to the strip's right end")
    rebuild_drawing(adapter, label="section C-C depth on its attached end")
    runs = _ink_segments(annotation)
    low = min((min(run[0], run[2]) for run in runs), default=float("inf"))
    print(f"TipCboreDepth ink after move: runs={runs} min_x={low}")
    if low < SLOT_SECTION_CENTER[0]:
        raise RuntimeError("C-C depth ink still crosses the strip after the move")


def _plan_basis_to_model(
    adapter: Any,
    view: Any,
    sheet_xy: tuple[float, float],
    origin: tuple[float, float, float],
    *,
    label: str,
) -> tuple[float, float, float]:
    """Invert a plan view's measured X/Z basis at ``origin``'s model Y.

    The R8 proof's inversion, shared by the cutter-note leader proof.
    """
    center = model_point_in_view(adapter, view, origin, label=f"{label} origin")
    px = model_point_in_view(
        adapter, view, (origin[0] + 0.001, origin[1], origin[2]), label=f"{label} X basis"
    )
    pz = model_point_in_view(
        adapter, view, (origin[0], origin[1], origin[2] + 0.001), label=f"{label} Z basis"
    )
    xx, xy = px[0] - center[0], px[1] - center[1]
    zx, zy = pz[0] - center[0], pz[1] - center[1]
    det = xx * zy - zx * xy
    if abs(det) < 1e-12:
        raise RuntimeError(f"{label} plan projection is singular")
    dx, dy = sheet_xy[0] - center[0], sheet_xy[1] - center[1]
    return (
        origin[0] + 0.001 * (dx * zy - zx * dy) / det,
        origin[1],
        origin[2] + 0.001 * (xx * dy - dx * xy) / det,
    )


def _add_cutter_note(adapter: Any, view: Any, note: CutterNote) -> Any:
    """Place one leadered cutter note, then prove its tip is on its arc.

    Same proof as the R8 radius: the leader tip read back off the sheet is
    inverted through the view's measured plan basis at each candidate edge's
    model Y, and the trimmed physical edge (``IEdge::GetClosestPointOn``) must
    lie within ``LEADER_TIP_BOUND_M`` of it.  Candidates are the named cut's
    own edges on the west end circle (radius and centre to 1e-6 m), limited
    to ``note.model_y_mm`` when the note names one face.
    """
    tip_xy = model_point_in_view(
        adapter, view, cutter_note_model_tip(note), label=f"{note.key} note tip"
    )
    drift = math.dist(tip_xy[:2], cutter_note_tip(note))
    # The detail's centre lands within 0.5 mm of DETAIL_CENTER (asserted by
    # _create_detail_view); the layout was checked against that point.
    if drift > 0.0006:
        raise RuntimeError(
            f"{note.key} note tip projects to {tip_xy[:2]}, layout expects "
            f"{cutter_note_tip(note)} ({drift * 1000:.3f} mm off)"
        )
    created = add_leader_note(
        adapter,
        note.text,
        text_xy=note.text_xy,
        attach_xy=(tip_xy[0], tip_xy[1]),
        label=f"{note.key} cutter note",
        view=view,
    )
    annotation = _early_bound(_early_bound(created, "INote").GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{note.key} cutter note has no text format")
    text_format.CharHeight = CUTTER_NOTE_CHAR_HEIGHT
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size the {note.key} cutter note")
    rebuild_drawing(adapter, label=f"{note.key} cutter note text height")

    points = [float(v) for v in (annotation.GetLeaderPointsAtIndex(0) or ())]
    if len(points) < 6:
        raise RuntimeError(f"{note.key} cutter note leader is unreadable")
    tip = (points[-3], points[-2])
    document = _early_bound(_early_bound(view, "IView").ReferencedDocument, "IModelDoc2")
    feature = _early_bound(
        _early_bound(document, "IPartDoc").FeatureByName(note.feature), "IFeature"
    )
    radius_m = note.radius_mm / 1000.0
    center_x = 0.002  # the west end arc's centre, +TIP_SCREW_HALF_TRAVEL
    center_z = TIP_SCREW_LOCAL_Z / 1000.0
    candidates: list[tuple[Any, tuple[float, ...]]] = []
    for raw_face in feature.GetFaces() or ():
        for raw_edge in _early_bound(raw_face, "IFace2").GetEdges() or ():
            edge = _early_bound(raw_edge, "IEdge")
            if any(int(adapter.swApp.IsSame(edge, item[0])) == 1 for item in candidates):
                continue
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            circle = tuple(float(value) for value in curve.CircleParams)
            if (
                abs(circle[6] - radius_m) > 1e-6
                or abs(circle[0] - center_x) > 1e-6
                or abs(circle[2] - center_z) > 1e-6
            ):
                continue
            if (
                note.model_y_mm is not None
                and abs(circle[1] - note.model_y_mm / 1000.0) > 1e-6
            ):
                continue
            candidates.append((edge, circle))
    if not candidates:
        raise RuntimeError(f"{note.feature} has no west end arc for the {note.key} note")
    distances = []
    for edge, circle in candidates:
        model_tip = _plan_basis_to_model(
            adapter, view, tip, circle[:3], label=f"{note.key} note arc"
        )
        closest = tuple(float(value) for value in edge.GetClosestPointOn(*model_tip))
        distance = math.dist(model_tip, closest[:3])
        distances.append(distance)
        print(
            f"{note.key} cutter note: tip_sheet_m={tip} arc_center_m={circle[:3]} "
            f"radius_m={circle[6]} tip_model_m={model_tip} "
            f"closest_model_m={closest[:3]} distance_m={distance}"
        )
    if not min(distances) <= LEADER_TIP_BOUND_M:
        raise RuntimeError(
            f"{note.key} cutter note leader misses its {note.feature} end arc "
            f"by {min(distances) * 1000:.4f} mm"
        )
    _telemetry.info(
        f"{note.key} cutter note leader lands on {note.feature}'s west end arc "
        f"({len(candidates)} candidate edge(s), {min(distances) * 1e6:.2f} um)"
    )
    return created


def _visible_plan_controls(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the pivot and post-mount rims from the plan view.

    The north-end and long-straight-side edges were dropped with the GD&T that
    referenced them (see ``build``) -- nothing else on this sheet attaches to
    them.
    """
    expected_radius_m = PIVOT_HOLE_DIA / 2000.0
    expected_mount_radius_m = blind_cut_dia_mm(POST_MOUNT_SPEC) / 2000.0
    pivot_edges: list[Any] = []
    mount_edges: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1), default=()
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            values = tuple(float(value) for value in curve.CircleParams)
            if abs(values[6] - expected_radius_m) <= 1e-6:
                pivot_edges.append(edge)
            if abs(values[6] - expected_mount_radius_m) <= 1e-6:
                mount_edges.append(edge)
    if not pivot_edges or len(mount_edges) < 2:
        raise RuntimeError("cone-platform plan view is missing pivot/mount controls")
    return pivot_edges[0], mount_edges[0]


def _horizontal_section_edge(
    view: Any, y_mm: float, *, label: str, prefer_right: bool = False
) -> Any:
    """Return a horizontal section edge on one broad-face station."""
    candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} section edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(value) * 1000.0 for value in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1] - y_mm) <= 0.01 and abs(p1[1] - y_mm) <= 0.01:
            candidates.append((abs(p1[0] - p0[0]), 0.5 * (p0[0] + p1[0]), edge))
    if not candidates:
        raise RuntimeError(f"pivot section has no {label} edge at y={y_mm:.3f} mm")
    key_index = 1 if prefer_right else 0
    return max(candidates, key=lambda item: item[key_index])[2]


def _add_section_hole_axis(adapter: Any, section: Any) -> None:
    """Draw the pivot-hole axis between the two cut slices of section A-A.

    The cut-face-only section shows the hole as a bare gap; without its axis a
    reader takes the right slice for an unrelated fragment.
    """
    radius_mm = PIVOT_HOLE_DIA / 2.0
    walls: dict[int, Any] = {}
    for raw_edge in visible_view_entities(section, 1, label="pivot hole wall edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(v) * 1000.0 for v in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(v) * 1000.0 for v in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1] - p1[1]) < 1.0:
            continue
        for side in (-1, 1):
            if all(abs(p[0] - side * radius_mm) <= 0.01 for p in (p0, p1)):
                walls[side] = edge
                print(f"pivot hole wall {side:+d}: {p0} -> {p1}")
    if set(walls) != {-1, 1}:
        raise RuntimeError(f"section A-A shows {len(walls)} pivot hole walls, expected 2")
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate section A-A for the hole axis")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for index, side in enumerate((-1, 1)):
        data = selection_manager.CreateSelectData()
        data.View = section
        if not _early_bound(walls[side], "IEntity").Select4(index > 0, data):
            raise RuntimeError(f"failed to select pivot hole wall {side:+d}")
    if int(selection_manager.GetSelectedObjectCount2(-1)) != 2:
        raise RuntimeError("pivot hole axis needs exactly the two wall edges selected")
    centerline = ddoc.InsertCenterLine2()
    draw.ClearSelection2(True)
    if centerline is None:
        raise RuntimeError("failed to insert the pivot hole axis in section A-A")
    rebuild_drawing(adapter, label="section A-A pivot hole axis")
    lines = tuple(_read_member(section, "GetCenterLines") or ())
    if not lines:
        raise RuntimeError("section A-A lost its pivot hole axis")
    print(f"section A-A centerlines: {len(lines)}")


def _section_edge_midpoint(
    adapter: Any, view: Any, edge: Any, *, label: str
) -> tuple[float, float]:
    """Return the sheet point at the middle of one broad-face section edge."""
    points = [
        tuple(float(value) for value in _early_bound(vertex, "IVertex").GetPoint())
        for vertex in (edge.GetStartVertex(), edge.GetEndVertex())
    ]
    middle = tuple(0.5 * (points[0][i] + points[1][i]) for i in range(3))
    if abs(middle[0]) * 1000.0 <= PIVOT_HOLE_DIA / 2.0 + 0.5:
        raise RuntimeError(f"{label} edge midpoint falls in the pivot hole: {middle}")
    sheet = model_point_in_view(adapter, view, middle, label=f"{label} edge midpoint")
    print(
        f"{label} finish attach: edge_model_m={points} middle_model_m={middle} "
        f"sheet_m=({sheet[0]:.5f},{sheet[1]:.5f})"
    )
    return (sheet[0], sheet[1])


def expected_corner_arcs(feature_name: str) -> int:
    """Visible plan arcs a corner fillet leaves: 2 where the W18 relief crosses it.

    Derived from the same overlap the part build credits in its fillet volume
    gate (``_north_fillet_relief_overlap``), so the drawing and the model agree
    on where the open relief splits a fillet's top edge.
    """
    label = feature_name.removeprefix("Corner")
    radius = {corner[0]: corner[3] for corner in _part._CORNERS}[label]
    return 2 if _part._north_fillet_relief_overlap(label, radius) > 0.0 else 1


def check_corner_arc_plan(
    name: str, plan: list[tuple[float, float, float]], expected: int
) -> None:
    """Exactly the expected owned arcs, all on one plan circle (x, z, radius)."""
    if len(plan) != expected:
        raise RuntimeError(
            f"expected {expected} owned visible {name} arc(s) at corner station, "
            f"found {len(plan)}"
        )
    if any(math.dist(item, plan[0]) > 1e-8 for item in plan[1:]):
        raise RuntimeError(f"{name} owned arcs do not share one plan circle: {plan!r}")


def _assert_corner_radius_attachment(
    adapter: Any, view: Any, annotations: list[Any], *,
    name: str, feature_name: str, radius_m: float, station_xy: tuple[float, float],
) -> None:
    """Prove a native radius dimension's arrow lies on its owned visible arc."""
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one native {name} radius annotation")
    annotation = _early_bound(matches[0], "IAnnotation")
    # Imported fillet dimensions can return unsupported/null annotation entities.
    # Record that API honestly; model-dimension ownership below is authoritative.
    entities = annotation.GetAttachedEntities3()
    entity_types = annotation.GetAttachedEntityTypes()
    print(
        f"{name} annotation entities_none={entities is None} "
        f"entity_nulls={tuple(item is None for item in (entities or ()))} types={entity_types!r}"
    )
    dangling = annotation.IsDangling()
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    owner = _early_bound(dimension.GetFeatureOwner(), "IFeature")
    print(f"{name} native model dimension owner={owner.Name!r} dangling={dangling!r}")
    if dangling is not False or str(owner.Name) != feature_name:
        raise RuntimeError(f"{name} is dangling or is not owned by native {feature_name}")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    arrows = [
        tuple(float(value) for value in data.GetArrowHeadAtIndex2(index))
        for index in range(int(data.GetArrowHeadCount()))
    ]
    if len(arrows) != 1 or len(arrows[0]) < 3:
        raise RuntimeError(f"expected one {name} arrow tip, found {arrows}")
    arrow = arrows[0]
    visible = visible_view_entities(view, 1, label=f"{name} visible corner edges")
    candidates = []
    for raw_face in owner.GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        if str(_early_bound(face.GetFeature(), "IFeature").Name) != feature_name:
            continue
        for raw_edge in face.GetEdges() or ():
            edge = _early_bound(raw_edge, "IEdge")
            if not any(int(adapter.swApp.IsSame(edge, item)) == 1 for item in visible):
                continue
            if any(int(adapter.swApp.IsSame(edge, item[0])) == 1 for item in candidates):
                continue
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            circle = tuple(float(value) for value in curve.CircleParams)
            if abs(circle[6] - radius_m) > 1e-8:
                continue
            center = model_point_in_view(adapter, view, circle[:3], label=f"{name} owned circle")
            if all(abs(center[i] - station_xy[i]) <= 0.001 for i in (0, 1)):
                candidates.append((edge, circle, center))
    # W18 (5db29554, run d9711228): the open pivot relief crosses the NW
    # fillet, so its plan arc is two physical edges on one circle -- one on
    # the 6.35 top, one on the 6.10 relief floor.  Every owned visible arc
    # must share the plan centre and radius; the arrow must land on one.
    plan = [(circle[0], circle[2], circle[6]) for _edge, circle, _center in candidates]
    check_corner_arc_plan(name, plan, expected_corner_arcs(feature_name))
    distances = []
    for edge, circle, center in candidates:
        # Invert the measured plan-view X/Z basis at this owned edge's model Y.
        px = model_point_in_view(adapter, view, (circle[0] + 0.001, circle[1], circle[2]), label=f"{name} X basis")
        pz = model_point_in_view(adapter, view, (circle[0], circle[1], circle[2] + 0.001), label=f"{name} Z basis")
        xx, xy = px[0] - center[0], px[1] - center[1]
        zx, zy = pz[0] - center[0], pz[1] - center[1]
        det = xx * zy - zx * xy
        if abs(det) < 1e-12:
            raise RuntimeError(f"{name} plan projection is singular")
        dx, dy = arrow[0] - center[0], arrow[1] - center[1]
        model_tip = (
            circle[0] + 0.001 * (dx * zy - zx * dy) / det,
            circle[1],
            circle[2] + 0.001 * (xx * dy - dx * xy) / det,
        )
        # IEdge, not ICurve: the closest point is on the trimmed physical edge.
        closest = tuple(float(value) for value in edge.GetClosestPointOn(*model_tip))
        trim = _early_bound(edge.GetCurveParams3(), "ICurveParamData")
        distance = math.dist(model_tip, closest[:3])
        distances.append(distance)
        print(
            f"{name} owned visible trimmed edge: arrow_sheet_m={arrow[:3]} radius_m={circle[6]} "
            f"center_model_m={circle[:3]} trim_u=({trim.UMinValue},{trim.UMaxValue}) "
            f"closest_u={closest[3]} arrow_model_m={model_tip} "
            f"closest_model_m={closest[:3]} distance_m={distance}"
        )
    if not min(distances) <= 0.00002:  # 0.01 mm on this 1:2 sheet; unchanged physical-edge bound.
        raise RuntimeError(f"{name} arrow does not land on its owned physical corner arc")
    # Which face's arc the arrow names: a reader should see the radius on the
    # 6.35 top outline, not the 6.10 relief floor (Main, 2026-09-24).
    hit = candidates[distances.index(min(distances))][1]
    _telemetry.info(
        f"{name} arrow lands on the arc at model y={hit[1] * 1000.0:.3f} mm "
        f"({len(candidates)} owned arc(s); plate top {PLATE_THICKNESS:.2f})"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-swing-platform source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Profile View Note",
            "Feature View Note",
            "Notch View Note",
            "Isometric View Note",
            "Pivot Relief Fit",
            "Post Mount Engagement",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Profile View Note",
            "Feature View Note",
            "Notch View Note",
            "Isometric View Note",
            "Pivot Relief Fit",
            "Post Mount Engagement",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Swing Platform Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone swing platform; wedge plate; pivot; lock notch",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    profile = place_view(
        adapter, str(SOURCE), "*Top", *PROFILE_CENTER, scale=(1, 2)
    )
    feature = place_view(
        adapter, str(SOURCE), "*Top", *FEATURE_CENTER, scale=(1, 2)
    )
    notch = place_view(adapter, str(SOURCE), "*Top", *NOTCH_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 3))
    for view in (profile, feature, notch, iso):
        set_hidden_lines_removed(adapter, view)

    pivot_xy = model_point_in_view(
        adapter, feature, (0.0, 0.0, 0.0), label="pivot section station"
    )
    feature_outline = tuple(float(value) for value in feature.GetOutline())
    section = create_section_view(
        adapter,
        feature,
        line_start=(feature_outline[0] - 0.002, pivot_xy[1]),
        line_end=(feature_outline[2] + 0.002, pivot_xy[1]),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="pivot bearing section",
    )
    cut = _early_bound(section.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="pivot section cut faces only")
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("pivot section retained geometry beyond the cutting plane")
    _position_section_label(adapter, section)
    set_hidden_lines_removed(adapter, section)
    _add_section_hole_axis(adapter, section)

    detail = _create_detail_view(
        adapter,
        feature,
        model_center_mm=(0.0, PLATE_THICKNESS, DETAIL_MODEL_Z),
        radius_mm=DETAIL_RADIUS_MM,
        view_xy=DETAIL_CENTER,
        detail_label="B",
        scale=DETAIL_SCALE,
        label="tip screw slot detail",
    )
    # Hidden edges dashed, so the underside counterbored slot reads.
    set_hidden_lines_visible(adapter, detail)
    profile_pivot = model_point_in_view(
        adapter, profile, (0.0, PLATE_THICKNESS / 1000.0, 0.0), label="profile pivot"
    )
    print(f"profile pivot: sheet_xy={profile_pivot[:2]} expected={PROFILE_PIVOT_XY}")
    if math.dist(profile_pivot[:2], PROFILE_PIVOT_XY) > 0.0005:
        # The C-C arrow clearances in the tests are laid out from it.
        _telemetry.warn(
            f"profile pivot landed at {profile_pivot[:2]}, layout assumes {PROFILE_PIVOT_XY}"
        )
    slot_ends = [
        model_point_in_view(adapter, profile, point, label=f"slot section end {index}")
        for index, point in enumerate(slot_section_line_model_points())
    ]
    slot_section = create_section_view(
        adapter,
        profile,
        line_start=slot_ends[0],
        line_end=slot_ends[1],
        view_xy=SLOT_SECTION_CENTER,
        section_label="C",
        scale=(1, 1),
        partial=False,
        label="tip screw slot section",
    )
    slot_cut = _early_bound(slot_section.GetSection(), "IDrSection")
    slot_cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="slot section cut faces only")
    _look_slot_section_south(adapter, profile, slot_section, slot_cut)
    set_hidden_lines_removed(adapter, slot_section)

    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="profile plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _hide_profile_cosmetic_threads(adapter, profile)
    feature_annotations = curate_view_dimensions(
        adapter,
        feature,
        keep=FEATURE_KEEP,
        view_label="feature plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Name the relief so the reader ties the width to the fit note; it is
    # open through the north edge (rule-12 W18), round-ended at the pivot.
    set_dimension_callouts(
        adapter,
        feature_annotations,
        {"PivotBearingReliefDia": RELIEF_WIDTH_CALLOUT},
    )
    notch_annotations = curate_view_dimensions(
        adapter,
        notch,
        keep=NOTCH_KEEP,
        view_label="notch plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _assert_notch_angle_in_wedge(adapter, notch, notch_annotations)
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="pivot section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    for annotation in section_annotations:
        if dimension_name(adapter, annotation) == "PlateThk":
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            for witness_index in (0, 1):
                ok, _use_doc, old_gap = display.GetWitnessLineGap(witness_index, False, 0.0)
                if ok is not True:
                    raise RuntimeError("plate thickness witness gap could not be read")
                # Measured native witness origin is x415; the actual cut edge
                # is x310.2. Leave a visible 1.2 mm gap at x309, without
                # changing the model dimension or hiding either witness.
                gap = float(old_gap) + 0.106
                if display.SetWitnessLineGap(witness_index, False, gap) is not True:
                    raise RuntimeError("plate thickness witness gap was refused")
                ok, use_doc, actual_gap = display.GetWitnessLineGap(witness_index, False, 0.0)
                if ok is not True or use_doc or abs(float(actual_gap) - gap) > 1e-8:
                    raise RuntimeError("plate thickness witness gap did not persist")
                print(f"PlateThk witness {witness_index}: old_gap_m={old_gap} gap_m={actual_gap}")
            rebuild_drawing(adapter, label="plate thickness cut-edge witness gaps")
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="tip screw slot detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _set_arrows_inside(adapter, detail_annotations, DETAIL_ARROWS_INSIDE)
    # U41: the thickness is the stock's, a reference with no band.
    thickness_annotations = [
        item for item in section_annotations
        if dimension_name(adapter, item) == "PlateThk"
    ]
    if len(thickness_annotations) != 1:
        raise RuntimeError("expected one native plate thickness")
    thickness_reference = set_reference_dimension(
        adapter, thickness_annotations[0], label="stock plate thickness reference"
    )
    set_dimension_callouts(
        adapter, thickness_annotations, {"PlateThk": PLATE_STOCK_CALLOUT}
    )
    slot_section_annotations = curate_view_dimensions(
        adapter,
        slot_section,
        keep=SLOT_SECTION_KEEP,
        view_label="tip screw slot section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _keep_depth_on_its_attached_end(adapter, slot_section_annotations)
    relief_annotations = [
        item for item in section_annotations
        if dimension_name(adapter, item) == "PivotBearingReliefDepth"
    ]
    if len(relief_annotations) != 1:
        raise RuntimeError("expected one native pivot relief depth")
    relief_reference = set_reference_dimension(
        adapter, relief_annotations[0], label="matched pivot relief reference depth"
    )
    annotations = [
        *profile_annotations,
        *feature_annotations,
        *notch_annotations,
        *section_annotations,
        *detail_annotations,
        *slot_section_annotations,
    ]
    if not auto_center_marks(adapter, feature, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to feature plan")

    pivot_edge, mount_edge = _visible_plan_controls(adapter, feature)
    # Below the section line, between the A arrows: right of the plate the
    # 189.26 dimension line crosses any callout wider than ~40 mm.
    add_native_hole_callout(
        adapter,
        feature,
        callout_xy=(0.215, 0.107),
        label="pivot close-clearance hole",
        edge=pivot_edge,
        process="DRILL",
    )
    add_native_hole_callout(
        adapter,
        feature,
        callout_xy=(0.200, 0.258),
        label="v2 post-mount tapped holes",
        edge=mount_edge,
    )
    # The section shows the top seat at the bottom.  Arrows land mid-face so
    # neither symbol reads as controlling a corner, hole wall or outer edge.
    seat_edge = _horizontal_section_edge(section, 6.35, label="top seat")
    add_surface_finish(
        adapter,
        section,
        symbol_xy=_shifted(0.291, 0.087),
        control=surface_finish_by_key(SURFACE_FINISHES, "post_seat"),
        label="post and tip-block seat finish",
        char_height=0.0025,
        entity=seat_edge,
        leader_attach_xy=_section_edge_midpoint(adapter, section, seat_edge, label="top seat"),
    )
    slide_edge = _horizontal_section_edge(
        section, 0.0, label="base slide", prefer_right=True
    )
    add_surface_finish(
        adapter,
        section,
        symbol_xy=BASE_SLIDE_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "base_slide"),
        label="base sliding-face finish",
        char_height=0.0025,
        entity=slide_edge,
        leader_attach_xy=_section_edge_midpoint(adapter, section, slide_edge, label="base slide"),
    )

    add_property_linked_note(adapter, "Profile View Note", 0.045, 0.085)
    add_property_linked_note(adapter, "Feature View Note", 0.150, 0.085)
    add_property_linked_note(adapter, "Notch View Note", *NOTCH_CAPTION_UPPER_LEFT)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.158)
    add_property_linked_note(
        adapter, "Post Mount Engagement", *ENGAGEMENT_NOTE_XY, char_height=0.0025
    )
    add_property_linked_note(
        adapter, "Pivot Relief Fit", *RELIEF_NOTE_XY, char_height=0.0025
    )
    cutter_notes = [
        _add_cutter_note(adapter, detail, cutter_note) for cutter_note in CUTTER_NOTES
    ]

    # Annotation insertion can invalidate the exported display geometry.
    for view in (profile, feature, notch, section, slot_section, iso):
        set_hidden_lines_removed(adapter, view)
    # Re-assert after the dimensions attach: the shared helper passes through
    # HLR, so the dashed edge set is regenerated, not a same-mode no-op.
    set_hidden_lines_visible(adapter, detail)
    # Last, after every annotation and display-mode regen could re-lay it.
    _position_view_label(
        adapter,
        detail,
        DETAIL_LABEL_LOWER_LEFT,
        label="detail B label",
        added_notes=cutter_notes,
    )
    _position_view_label(
        adapter,
        slot_section,
        SLOT_SECTION_LABEL_LOWER_LEFT,
        label="section C-C label",
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if (str(relief_reference.GetText(1)), str(relief_reference.GetText(2))) != ("(", ")"):
        raise RuntimeError("pivot relief reference state did not persist")
    if (
        str(thickness_reference.GetText(1)),
        str(thickness_reference.GetText(2)),
    ) != ("(", ")"):
        raise RuntimeError("stock plate thickness reference state did not persist")
    for name, feature_name, radius_m, station_xy in (
        ("CornerSWR", "CornerSW", 0.005, (0.0875, 0.2433)),
        ("CornerNWR", "CornerNW", 0.008, (0.0723, 0.1382)),
        ("CornerNER", "CornerNE", 0.010, (0.0686, 0.1392)),
        ("CornerSER", "CornerSE", 0.012, (0.0660, 0.2398)),
    ):
        _assert_corner_radius_attachment(
            adapter, profile, profile_annotations,
            name=name, feature_name=feature_name, radius_m=radius_m, station_xy=station_xy,
        )
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("pivot section lost its cut-only display after annotation")
    for face_name, model_y in (
        ("post_seat", PLATE_THICKNESS / 1000.0),
        ("base_slide", 0.0),
    ):
        projected = model_point_in_view(
            adapter, section, (0.0, model_y, 0.0), label=f"{face_name} projection"
        )
        print(
            f"section face {face_name}: model_y_mm={model_y * 1000:.3f} "
            f"sheet_xy_mm=({projected[0] * 1000:.3f},{projected[1] * 1000:.3f})"
        )
    for sheet_geometry in collect_document(adapter):
        print(describe_sheet(sheet_geometry))
        thickness_geometry = [
            item for item in sheet_geometry.annotations if item.label == "PlateThk"
        ]
        if len(thickness_geometry) != 1:
            raise RuntimeError("expected one measured plate thickness annotation")
        witnesses = [
            segment for segment in thickness_geometry[0].segments
            if abs(segment.y0 - segment.y1) < 1e-8
            and any(
                abs(segment.y0 - SECTION_SHIFT[1] - level) < 0.0001
                for level in (0.09865, 0.11135)
            )
        ]
        if len(witnesses) != 2 or any(
            abs(max(segment.x0, segment.x1) - SECTION_SHIFT[0] - 0.309) > 0.0005
            or abs(min(segment.x0, segment.x1) - SECTION_SHIFT[0] - 0.299) > 0.0005
            for segment in witnesses
        ):
            raise RuntimeError(f"plate thickness witnesses did not shorten to the cut edge: {witnesses}")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Swing Platform Manufacturing Drawing",
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
