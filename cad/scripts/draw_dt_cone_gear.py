r"""Create the complete cone-gear batch drawing package (MHA-DT-03).

Every configured family member T012..T120 by six receives a standalone sheet
(T006 is MHA-DT-37, draw_dt_cone_tip_gear).  Each sheet selects its own part
configuration, imports the native model-owned blank diameter, bore (T012..T024
a round reamed bore: its diameter; T030..T120 round with a hub keyway:
diameter, keyway width, T and clock), face width, driving
circular-tooth-thickness requirement and functional root-envelope limits,
plus the actual finite cutter recipe and bounded carrying-contact data.
The native imported bands remain model-owned.

There are no datums, feature-control frames or finish symbols: the bore is a
bonded or keyed fit that does not run (drawing-guidelines.md rule 6).  Hidden
lines communicate no additional manufacturing fact on these through-bored
spur gears, so every view remains hidden-lines-removed.  The side view stays
in projection with the front view's bore axis; its face width hangs below it,
clear of the Gear Data block. The circular pitch thickness uses a
construction inspection witness of the actual arc size, not an ideal chord
oracle; root MIN/MAX use the actual radial-envelope witness.  A plain round
bore (T012..T024) prints its diameter on the front view; a keyed bore
(T030..T120) prints in an enlarged bore view, DETAIL A, a cropped *Front model
view at a scale that renders the bore at least ``BORE_VIEW_BORE_MIN`` across;
its lettered boundary rings the bore on the front view, and both views
centre-mark the bore. Numbered notes name each mate once: note 1 the bore's fit (bonded on
MHA-DT-37's spigot, T012/T018; bonded on MHA-DT-04's land 2, T024; sliding
on MHA-DT-04 and the MHA-DT-VN-71 key, T030..T120), note 2 the mesh with
MHA-DT-12. The part saves both construction sketches hidden; only the front
view, which dimensions them, shows them.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    curate_dimensions,
    dimension_name,
    place_view,
    view_name,
)

import _config
from _check import check
from _com import _early_bound
from _cone_gear_readback import assert_saved_configuration_topology
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_annotation_extent import callout_ink, move_annotation
from _drawing_dimension_import import _INSERT_DIMS_MARKED, delete_unnamed_imports
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
)
from _drawing_edges import visible_view_entities
import _drawing_hidden_sketches as hidden_sketches
from _drawing_layout_collect import check_drawing_layout
from _drawing_leaders import (
    ARROW_TEXT_CLEARANCE,
    dimension_segments,
    set_near_side_diameter,
)
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _fit_deviations import deviations
from _layout_geometry import Box, Segment, segment_box_distance
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _pdf_ink import PageInk, read_pdf_ink
from _session import run_build
import _telemetry
import cone_land_key
from cone_shaft_land_bands import SECTION_DIA_BANDS
from dt_cone_gear_notes import (
    DRAWING_DIMENSIONS,
    TOOTH_EDGE_NOTE,
)
from dt_cone_gear_spec import (
    BORE_BAND_PLACES,
    BORE_SKETCH,
    CONFIGURATION_TEETH,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    KEYED_BORE_SKETCH,
    KEYED_LAND,
    SPIGOT_TEETH,
    WEB_REFERENCE_ANGLE_DEG,
    WEB_REFERENCE_TEETH,
    bore_dia_band,
    bore_dia_mm,
    bore_reach_mm,
    blank_dia_band,
    inch_text,
    keyway_top_offset_mm,
    tooth_thickness_band,
    floor_limits_mm,
    gap_floor_deviations_mm,
    keyed,
    outside_dia_mm,
    tooth_thickness_mm,
)
import dt_cone_gear_spec

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["dt_cone_gear"]
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

SHEET_NAMES = tuple(f"T{teeth:03d}" for teeth in CONFIGURATION_TEETH)
# Discrete standard ratios keep both the tip and common face width legible.
# The enlarged T120 blank takes 1:1 so its view stays in the existing lanes.
_SCALE_BY_TEETH = {
    12: (6.0, 1.0),
    18: (5.0, 1.0),
    24: (4.0, 1.0),
    30: (3.0, 1.0),
    36: (3.0, 1.0),
    42: (3.0, 1.0),
    48: (5.0, 2.0),
    54: (5.0, 2.0),
    60: (2.0, 1.0),
    66: (2.0, 1.0),
    72: (2.0, 1.0),
    78: (2.0, 1.0),
    84: (2.0, 1.0),
    90: (3.0, 2.0),
    96: (3.0, 2.0),
    102: (3.0, 2.0),
    108: (3.0, 2.0),
    114: (3.0, 2.0),
    120: (1.0, 1.0),
}
SHEET_SCALES = {f"T{teeth:03d}": _SCALE_BY_TEETH[teeth] for teeth in CONFIGURATION_TEETH}
SHEET_SCALE = SHEET_SCALES[SHEET_NAMES[0]]

FRONT_CENTER = (0.105, 0.150)
# Projection-aligned with the front view's bore axis (codex, 2026-09-23: the
# 0.140 offset that cleared FaceWidth from Gear Data broke the alignment).
RIGHT_CENTER = (0.245, FRONT_CENTER[1])
ISO_CENTER = (0.355, 0.150)
# The keyed bore (T030..T120) prints in its own enlarged view: a *Front model
# view of the sheet's configuration, cropped by a circle round the bore (the
# MHA-DT-VN-61 pattern of draw_amplitude_bar and draw_pinion_arbor; their
# native detail views would not take moved or imported dimensions).  The view
# sits lower left, under the front view and left of the thickness callout,
# and carries every keyed-bore dimension: diameter, keyway width, T, clock.
# A plain round bore (T012..T024) has no shape to enlarge: its diameter reads
# on the front view (``front_bore_dia_xy``; round 2 machinist review of the
# C1-keyed sheets, rule 1).
# The layout audit compares view OUTLINES, not circles: GetOutline pads the
# front view ~5.5 mm and a cropped view 10.1-10.75 mm past its crop circle
# (farm run 20260929T061328212Z at 70d2e52: T084's front box [54.8, 99.8, 155.2,
# 200.2] met this view's [15.2, 29.2, 88.8, 102.8] when it stood at y 0.066
# with a 7 mm margin). At y 0.060 with 3 mm the box clears T120's, the
# largest tip circle on the set, by ~4 mm and the title stays above the
# 12.7 mm zone band.
BORE_VIEW_CENTER = (0.052, 0.060)
# Each sheet takes the smallest useful ladder ratio above its own, reading the
# current web-qualified terminal land rather than assuming the old 1/16 seat.
BORE_VIEW_BORE_MIN = 0.028
BORE_VIEW_SCALE_LADDER = (
    (4.0, 1.0), (5.0, 1.0), (10.0, 1.0), (20.0, 1.0), (40.0, 1.0),
)
# Gear body kept round the bore inside the crop circle, sheet metres. The
# crop prints no outline (``_crop_bore_view``): drawn, its circle stood 3 mm
# outside the bore and the diameter's outside arrow spanned exactly that
# ring, so the Ø read as landing on the unlabelled circle (ENFORCE round 1
# of #971). Unprinted, the ring only spaces the bore from its callouts.
BORE_VIEW_CROP_MARGIN = 0.0015
# The view's title stands this far under the crop circle, below the
# across-flat callout's dimension line, the block's bottom edge. The block is
# centred on its SetPosition point, ~5.3 mm a row; the flag's line under
# BORE ACROSS FLAT adds one, so the point drops half a row less than the
# 5 mm it stood at and the bottom stays put.
BORE_VIEW_AF_DROP = 0.0025
# The view's title stands this far under the crop circle: a keyway's T text
# stands right of it, so the title rises under T's dimension line instead of
# under its text, the larger crop circle (the keyway's corners) would
# otherwise push it into the sheet's zone band.
KEYED_BORE_VIEW_LABEL_DROP = 0.0135
# The diameter's text stands this far above the crop circle (6 mm with the
# value alone): the block is centred there, and the lines under the value
# (two with the mate, one with the note flag) would lower the leader
# shoulder under it ~2.7 mm a line, onto the bore.
BORE_VIEW_DIA_LIFT = 0.0115
# The across-flat text stands OUTSIDE its witnesses, right of the flat's, as
# MHA-DT-07's does. Centred between them, its lines (~2.65 mm a character in
# the #1128 full-5 render) ran wider than the 29-35 mm witness span on every
# sheet, so both witness lines crossed the callout, and its tolerance stack
# sat on the diameter leader's lower end (machinist review of full-5).
# BORE_VIEW_AF_HALF_WIDTH is half the widest line it was sized for, the
# 20-character SLIDES ON MHA-DT-04 (now in note 1), rounded up; the narrower
# BORE ACROSS FLAT keeps more air. The text's left edge clears the flat's
# witness by BORE_VIEW_AF_GAP.
BORE_VIEW_AF_GAP = 0.004
BORE_VIEW_AF_HALF_WIDTH = 0.027
# The bore axis must land within 0.1 mm of BORE_VIEW_CENTER after the move
# (draw_amplitude_bar's detail tolerance), and the title within 1 mm.
BORE_VIEW_POSITION_TOL_M = 1e-4
NOTE_CENTRING_TOL_M = 0.001
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
CENTER_MARK_SINGLE = 2  # swCenterMarkStyle_e.swCenterMark_Single
# Imported, a clock keeps its sketch's quadrant wherever its text goes. Left
# between the flat's upper half and the -X centreline, its arc swept the
# diameter's upper-left leader lane, and on the 4:1 sheets it crossed that
# leader's shoulder (T030-T120, run 20260929T064504232Z).
# ``_sweep_clock_right_of_flat`` flips it into the quadrant right of the
# flat (keyway top) and above the axis. Its arc may overrun the flat or the
# axis by CLOCK_ARC_OVERRUN and must centre on the flat/axis crossing within
# CLOCK_ARC_CENTRE_TOL (sheet metres).
CLOCK_ARC_OVERRUN = 0.0003
CLOCK_ARC_CENTRE_TOL = 0.0005
CLOCK_FLIPS = ("SupplementaryAngle", "VerticallyOppositeAngle", "SupplementaryAngle")
# Top-aligned with the numbered notes: the 14-line block (header + 13
# rows) measured 49.1 mm tall natively (e91d2581 layout audit), 3.51 mm a
# line; the 15-line block ends ~52.6 mm down, still above the largest side
# view (top 0.197) with FaceWidth below it.
GEAR_DATA_POS = (0.215, 0.263)
# Rendered height budget of the Gear Data block, for the layout test.
GEAR_DATA_HEIGHT = 0.056
# The numbered notes (``sheet_notes``) are the sheet's only notes, top-left,
# above the front view's dimensions; their ~100 characters (1.79 mm each at
# 2.5 mm) end left of Gear Data. The part's "Manufacturing Notes" property
# (QTY) is not printed: the title block gives quantity (rule 7, round 4 of
# the fan-out).
NUMBERED_NOTES_POS = (0.015, 0.263)


# Each tight band names its mate and fit (drawing-guidelines rule 4; ENFORCE
# round 1 of #971 found them only in Gear Data, or nowhere). A mate serving
# several dimensions is named once, in one numbered note those dimensions
# flag (rule 4; screen of f21dfcdd2ba7): note 1 holds the bore's fit (bonded
# on MHA-DT-37's spigot, T012/T018; bonded on MHA-DT-04's land 2, T024;
# sliding on MHA-DT-04 and the MHA-DT-VN-71 key, T030..T120), note 2 the
# teeth's mesh with MHA-DT-12 (``sheet_notes``).  The bonded notes name the
# fit and its mate only: the compound is MHA-DT-00's bonding step's (rule 23).
SHAFT_MATE = "MHA-DT-04"
# A matched pair names its mate by name and number (rule 4; round-1 review
# of the fan-out: note 1 named MHA-DT-04 by number only, and no land).
SHAFT_NAME = str(_config.parts("dt-cone-gear-shaft")["title"]).upper()
_TIP_GEAR = _config.parts("dt-cone-tip-gear")
TIP_GEAR_MATE = str(_TIP_GEAR["number"]).strip().upper()  # MHA-DT-37
TIP_GEAR_NAME = str(_TIP_GEAR["title"]).upper()
# The land T024 is bonded on (MHA-DT-04's SECTIONS: journal, land 1, land 2).
BONDED_LAND = 2
CYLINDER_MATE = "MHA-DT-12"
# Land 1's key (owner decision 2026-11-09, C1 keyed, PR #1992), named by
# number like the shaft.
KEY_MATE = "MHA-DT-VN-71"
BORE_NOTE_NUMBER = 1
TEETH_NOTE_NUMBER = 2
BORE_NOTE_FLAG = f"SEE NOTE {BORE_NOTE_NUMBER}"
TEETH_NOTE_FLAG = f"SEE NOTE {TEETH_NOTE_NUMBER}"
DIMENSION_CALLOUTS = {
    # Every bore is round and reamed (owner decision 2026-11-09: no D-bore
    # remains, so the 2026-09-29 no-process-word ruling, which applied to the
    # D-bores only, no longer bears on this part): REAM (rule 7), the flag
    # under the value.
    "BoreCutDia": f"REAM THRU\n{BORE_NOTE_FLAG}",
    # The keyed bore (T030..T120) is round, so it takes the fit bore's REAM
    # (rule 7); its keyway's width band is the requirement, with no process
    # word.  T reads from its witnesses (keyway top, far side of the bore):
    # a size carries its value, band and flag (machinist review of the
    # C1-keyed sheets dropped KEYWAY TO FAR SIDE).
    "KeyedBoreDia": f"REAM THRU\n{BORE_NOTE_FLAG}",
    "KeywayWidth": BORE_NOTE_FLAG,
    "KeywayT": BORE_NOTE_FLAG,
    # The keyway's centreline runs through the bore axis and the +X tooth's
    # centre; the bore view crops the teeth off, so the callout names the
    # reference its centre-mark line stands for, the line the front view's
    # mark draws through that tooth (front_centre_mark_arms_mm).
    "KeywayClock": "TO TOOTH CENTERLINE",
    # The text is the same on every sheet: offset (OffsetText), the imported
    # model dimension printed the LAST sheet's below-text on all of them (T006
    # printed T120's "ON PITCH CIRCLE Ø63.500", farm runs of 746809f62 and
    # 5000ea76b), so no per-configuration size can ride on it. The name
    # stands over the value (CALLOUTS_ABOVE) and GEAR DATA prints the pitch
    # diameter it is measured on: the callout keeps two lines of words
    # (rule 7; screen of f21dfcdd2ba7 counted three). The short flag is the
    # bottom row, so the shelf's leader closes on the block clear of it.
    "ToothThickness": TEETH_NOTE_FLAG,
    # The origin circle is an inspection witness, not the off-centre root arc.
    "FloorDia": f"ROOT ENVELOPE\n{TEETH_NOTE_FLAG}",
    # The cone set is a solid stack on the shaft; each gear's width sets the
    # stations (user ruling 2026-09-28, spec FACE_WIDTH).
    "FaceWidth": f"20-GEAR STACK\nON {SHAFT_MATE}",
    # RV-03's accepted T012 web (cad/config/parts/dt-cone-gear.yaml): what the
    # single limit bounds, at the value.
    "WebMin": "WEB, BORE TO ROOT",
}


# Text over the value. One line each: SOLIDWORKS drops a multi-line callout
# above a value from the print (ENFORCE round 2 of #971: every two-line one
# went unmatched in the PDF; draw_ch_amplitude_bar r1).
CALLOUTS_ABOVE = {
    "ToothThickness": "CIRCULAR TOOTH THICKNESS",
    "BlankDia": TEETH_NOTE_FLAG,
    "KeywayClock": CLOCK_REASON,
}
if any("\n" in text for text in CALLOUTS_ABOVE.values()):
    raise AssertionError("an above-callout with a line break does not print")


def _inch_limits(lower_mm: float, upper_mm: float) -> str:
    return f"{inch_text(lower_mm, 4)}-{inch_text(upper_mm, 4)}"


def bore_clearances_mm(teeth: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """((min, max) round, (min, max) keyway-to-key) clearance of a keyed
    sheet's bore on MHA-DT-04's land 1, from the parts' printed limits.

    Bore and land share their nominals (gear_seat_fit), so the round
    clearance is the bore's deviation less the land's; the keyway's is its
    width's against the key's (cone_land_key).
    """
    if not keyed(teeth):
        raise ValueError(f"T{teeth:03d} is bonded: its clearance is bond_clearance_mm")
    land_upper, land_lower = SECTION_DIA_BANDS[KEYED_LAND]
    bore_upper, bore_lower = bore_dia_band(teeth)
    round_fit = (bore_lower - land_upper, bore_upper - land_lower)
    return round_fit, cone_land_key.KEYWAY_SIDE_CLEARANCE_MM


def bonded_fit_note(teeth: int) -> str:
    """Note 1 of a round-bored sheet: the bonded slip fit and its mate."""
    if teeth in SPIGOT_TEETH:
        mate = f"{TIP_GEAR_NAME} {TIP_GEAR_MATE} SPIGOT"
    else:
        mate = f"{SHAFT_NAME} {SHAFT_MATE}, LAND {BONDED_LAND}"
    return f"{BORE_NOTE_NUMBER}. BONDED SLIP FIT ON {mate}."


def sheet_notes(teeth: int) -> str:
    """The sheet's numbered notes, flagged from the bore and teeth callouts.

    Note 1 is the bore's fit (rule 4).  A keyed bore's bands are narrower
    than the shop's turned and milled rows, so it is made to the measured
    land, with the clearance the parts' limits give as REF, and names the
    key its keyway slides on.  A round bore is bonded (owner decision
    2026-11-09, C1 keyed, PR #1992): the note names the fit and its mate.
    Note 2 names the mesh and the fit route of the tip, thickness and root
    bands: the over-pins and assembly backlash acceptances in GEAR DATA; it
    carries the teeth's do-not-cut, flagged to them rather than in a general
    block.
    """
    if keyed(teeth):
        (round_min, round_max), (key_min, key_max) = bore_clearances_mm(teeth)
        land = f"\u00d8{inch_text(bore_dia_mm(teeth), BORE_BAND_PLACES)} LAND"
        fit: tuple[str, ...] = (
            f"{BORE_NOTE_NUMBER}. SLIDING FIT ON {SHAFT_NAME} {SHAFT_MATE}, {land}, "
            f"AND KEY {KEY_MATE}:",
            "   BORE MADE TO THE MEASURED LAND "
            f"(CLEARANCE {_inch_limits(round_min, round_max)} ON \u00d8, "
            f"{_inch_limits(key_min, key_max)} KEYWAY TO KEY).",
        )
    else:
        fit = (bonded_fit_note(teeth),)
    return "\n".join((
        *fit,
        f"{TEETH_NOTE_NUMBER}. TEETH MESH WITH {CYLINDER_MATE}: ACCEPT OVER PINS, "
        "THEN BY BACKLASH AT ASSEMBLY,",
        f"   PER GEAR DATA. {TOOTH_EDGE_NOTE}",
    ))


def sheet_dimension_names(teeth: int) -> set[str]:
    """The model dimensions the sheet prints: every marked one but the other
    bore's, and RV-03's web on the T012 sheet only."""
    other = dt_cone_gear_spec.DRAWING_DIMENSIONS[
        BORE_SKETCH if keyed(teeth) else KEYED_BORE_SKETCH
    ]
    names = set().union(*DRAWING_DIMENSIONS.values()) - other
    if teeth != WEB_REFERENCE_TEETH:
        names.discard("WebMin")
    return names


def rendered_half_od(teeth: int) -> float:
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    return outside_dia_mm(teeth) * numerator / (denominator * 2000.0)


def rendered_half_face_width(teeth: int) -> float:
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    return FACE_WIDTH * numerator / (denominator * 2000.0)


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


def thickness_arrow_reach_y(teeth: int) -> float:
    """Sheet y where the thickness dimension's upper arrow tail ends.

    The upper witness stands half the tooth thickness above the bore axis at
    sheet scale (the arc thickness, an upper bound on the pitch chord it
    witnesses), and one outside arrow runs on past it.
    """
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    half_thickness = tooth_thickness_mm(teeth) * numerator / (denominator * 2000.0)
    return FRONT_CENTER[1] + half_thickness + DIMENSION_ARROW_LENGTH


def floor_dia_y(teeth: int) -> float:
    """Anchor y of the gap-floor stack: its usual place above the thickness
    witness, raised where that would put the shelf within the fleet's
    arrow-to-text clearance of the thickness arrow's tail."""
    usual = FRONT_CENTER[1] + 0.6 * rendered_half_od(teeth) + FLOOR_DIA_RISE
    lowest = thickness_arrow_reach_y(teeth) + ARROW_TEXT_CLEARANCE + FLOOR_STACK_HALF_HEIGHT
    return max(usual, lowest)


def _assert_dimension_arrow_length(drawing: Any) -> None:
    """Refuse a template whose arrow length is not the one the layout assumes."""
    extension = _early_bound(
        _early_bound(drawing, "IModelDoc2").Extension, "IModelDocExtension"
    )
    live = float(extension.GetUserPreferenceDouble(_PREF_ARROW_LENGTH, _PREF_OPT_NONE))
    if abs(live - DIMENSION_ARROW_LENGTH) > 1e-6:
        raise RuntimeError(
            f"drawing arrow length reads {live * 1000.0:.3f} mm; the gap-floor "
            f"stack is placed for {DIMENSION_ARROW_LENGTH * 1000.0:.3f} mm"
        )
    _telemetry.info(f"drawing arrow length {live * 1000.0:.3f} mm")


# RV-03's T012 web text sits on its own dimension line, carried outboard past
# the tip circle by this much (sheet metres).  Offset square to the line
# (r3, r4 reviews), the extension lines ran through the text.
WEB_MIN_TEXT_OUTBOARD = 0.012


def web_min_text_xy() -> tuple[float, float]:
    """Sheet point of the T012 web text: on its radial line, outside the teeth."""
    reach = rendered_half_od(WEB_REFERENCE_TEETH) + WEB_MIN_TEXT_OUTBOARD
    angle = math.radians(WEB_REFERENCE_ANGLE_DEG)
    return (
        FRONT_CENTER[0] + reach * math.cos(angle),
        FRONT_CENTER[1] + reach * math.sin(angle),
    )


def front_keep(teeth: int) -> dict[str, tuple[float, float]]:
    half_od = rendered_half_od(teeth)
    keep = {
        "FloorDia": (FRONT_CENTER[0] + half_od + FLOOR_DIA_GAP_X, floor_dia_y(teeth)),
        # Vertical dimension on the +X tooth: the anchor's x places its
        # line just right of the tip circle. Its y is where the import first
        # hangs the text, below the gear; the text then leaves the line for
        # its own shelf (``_shelve_tooth_thickness``).
        "ToothThickness": (
            FRONT_CENTER[0] + half_od + 0.014,
            FRONT_CENTER[1] - half_od - 0.0225,
        ),
    }
    # Only the T012 sheet states RV-03's web; no other sheet shows its sketch.
    if teeth == WEB_REFERENCE_TEETH:
        keep["WebMin"] = web_min_text_xy()
    # A plain round bore reads on the front view; a keyed one in DETAIL A.
    if not keyed(teeth):
        keep["BoreCutDia"] = front_bore_dia_xy(teeth)
    return keep


# The round bore's callout block (Ø, value and band over REAM THRU and the
# flag) round its SetPosition point, measured on T012..T024 in the round-2
# farm run 20261110T035403233Z: x -16.3..+16.3 mm, y -10.1..+9.0 mm, its
# leader shoulder along the bottom edge. The block's lower-right corner stands
# FRONT_BORE_DIA_REACH outside the tip circle at FRONT_BORE_DIA_ANGLE_DEG,
# the one front-view diagonal no line takes (the centre mark runs square, the
# root envelope's leader comes in from the upper right, T012's web runs down
# left and the thickness witnesses run right): the radial leader crosses the
# teeth to the bore's rim and nothing else.
FRONT_BORE_DIA_TEXT_HALF_WIDTH = 0.0165
FRONT_BORE_DIA_TEXT_DROP = 0.0101
FRONT_BORE_DIA_REACH = 0.005
FRONT_BORE_DIA_ANGLE_DEG = 135.0


def front_bore_dia_xy(teeth: int) -> tuple[float, float]:
    """Sheet point of a round bore's diameter text, upper left of the gear."""
    reach = rendered_half_od(teeth) + FRONT_BORE_DIA_REACH
    angle = math.radians(FRONT_BORE_DIA_ANGLE_DEG)
    return (
        FRONT_CENTER[0] + reach * math.cos(angle) - FRONT_BORE_DIA_TEXT_HALF_WIDTH,
        FRONT_CENTER[1] + reach * math.sin(angle) + FRONT_BORE_DIA_TEXT_DROP,
    )


def tooth_thickness_shelf(teeth: int) -> tuple[float, float]:
    """Sheet point where the thickness text's shelf starts: the text gap
    right of its dimension line, the shelf drop under the root-envelope
    stack's anchor."""
    line_x = front_keep(teeth)["ToothThickness"][0]
    shelf_y = floor_dia_y(teeth) - TOOTH_THICKNESS_SHELF_DROP
    return line_x + TOOTH_THICKNESS_TEXT_GAP, shelf_y


def bore_view_scale(teeth: int) -> tuple[float, float]:
    """The bore view's ratio: the smallest ladder ratio above the sheet's own
    that renders the bore at least ``BORE_VIEW_BORE_MIN`` across."""
    sheet_numerator, sheet_denominator = _SCALE_BY_TEETH[teeth]
    sheet_ratio = sheet_numerator / sheet_denominator
    for numerator, denominator in BORE_VIEW_SCALE_LADDER:
        ratio = numerator / denominator
        if ratio > sheet_ratio and bore_dia_mm(teeth) * ratio / 1000.0 >= BORE_VIEW_BORE_MIN:
            return numerator, denominator
    raise ValueError(f"no bore-view scale renders the T{teeth:03d} bore legibly")


def _bore_view_ratio(teeth: int) -> float:
    numerator, denominator = bore_view_scale(teeth)
    return numerator / denominator


def bore_view_crop_radius(teeth: int) -> float:
    """Sheet radius of the bore view's crop circle round the bore axis: the
    bore's reach (a keyway's top corners) plus the margin."""
    return bore_reach_mm(teeth) * _bore_view_ratio(teeth) / 1000.0 + BORE_VIEW_CROP_MARGIN


def clock_dimension_name(teeth: int) -> str:
    """The sheet's clock: the keyway's top to the centreline (keyed sheets
    only; a bonded round bore carries no clock)."""
    if not keyed(teeth):
        raise ValueError(f"T{teeth:03d}'s round bonded bore carries no clock")
    return "KeywayClock"


def bore_clock_vertex(teeth: int) -> tuple[float, float]:
    """Sheet point where the keyway top crosses the bore's horizontal
    centreline: the clock dimension's vertex."""
    top = keyway_top_offset_mm(teeth) * _bore_view_ratio(teeth) / 1000.0
    return BORE_VIEW_CENTER[0] + top, BORE_VIEW_CENTER[1]


# The keyway's width (T030..T120) prints right of the crop circle under the
# axis: its dimension line stands at the text, its witnesses run right from
# the keyway top's corners. Its block (value and band over the note flag,
# two rows) stands KEYWAY_WIDTH_TEXT_GAP right of the crop circle and its
# top KEYWAY_WIDTH_TEXT_DROP + ARROW_TEXT_CLEARANCE under the lower witness,
# where every keyed sheet has printed it; T's text then stands right of it,
# so T's dimension line runs on under it.
KEYWAY_WIDTH_TEXT_HALF_WIDTH = 0.014
KEYWAY_WIDTH_TEXT_HALF_HEIGHT = 0.006
KEYWAY_WIDTH_TEXT_GAP = 0.002
KEYWAY_WIDTH_TEXT_DROP = 0.0036


def bore_view_keep(teeth: int) -> dict[str, tuple[float, float]]:
    """Text positions of the keyed bore's dimensions round the bore view; a
    round bore has no bore view (``front_keep``).

    The diameter's leader runs in from upper left.  T's dimension line hangs
    under the crop circle between its witnesses (the arc's -X point and the
    keyway top) and runs on right to its text, which stands outside that
    witness and right of the keyway width's block; the clock's arc sweeps the
    quadrant between the keyway top's upper half and the +X centre-mark line
    (``_sweep_clock_right_of_flat``), its text right of the circle and raised
    clear of the axis line and the arc's arrowhead on it (BORE_CLOCK_TEXT_*).
    The keyway width's text mirrors the clock's under the axis.
    """
    if not keyed(teeth):
        return {}
    x, y = BORE_VIEW_CENTER
    crop = bore_view_crop_radius(teeth)
    # 3 mm right of x - 0.022: the inch seat band (+0.04572/+0.0254)
    # ran the text 1.6 mm past the left inner border (#290 batch 0).
    diameter = (x - 0.019, y + crop + BORE_VIEW_DIA_LIFT)
    ratio = _bore_view_ratio(teeth)
    top = keyway_top_offset_mm(teeth) * ratio / 1000.0
    clock = (
        x + crop + BORE_CLOCK_TEXT_GAP + BORE_CLOCK_TEXT_HALF_WIDTH,
        y + BORE_CLOCK_ARROW_LENGTH + ARROW_TEXT_CLEARANCE + BORE_CLOCK_TEXT_HALF_HEIGHT,
    )
    width_right = x + crop + BORE_CLOCK_TEXT_GAP + 2.0 * KEYWAY_WIDTH_TEXT_HALF_WIDTH
    half_width = dt_cone_gear_spec.KEYWAY_HALF_WIDTH_MM * ratio / 1000.0
    return {
        "KeyedBoreDia": diameter,
        # Under the lower witness and the arrow that ends on it.
        "KeywayWidth": (
            width_right - KEYWAY_WIDTH_TEXT_HALF_WIDTH,
            y - half_width - KEYWAY_WIDTH_TEXT_DROP - ARROW_TEXT_CLEARANCE
            - KEYWAY_WIDTH_TEXT_HALF_HEIGHT,
        ),
        "KeywayT": (
            max(x + top, width_right) + BORE_VIEW_AF_GAP + BORE_VIEW_AF_HALF_WIDTH,
            y - crop - BORE_VIEW_AF_DROP,
        ),
    }


# Rule 9: an enlarged view carries a letter, and its boundary, with the same
# letter, sits on its parent (screen of f21dfcdd2ba7: "BORE PROFILE" was
# named in prose only). DETAIL A is the bore view, its boundary ringing the
# bore on the front view.
BORE_DETAIL_LETTER = "A"


def bore_view_label(teeth: int) -> str:
    numerator, denominator = bore_view_scale(teeth)
    return f"DETAIL {BORE_DETAIL_LETTER}\nSCALE {numerator:g} : {denominator:g}"


def bore_view_label_top(teeth: int) -> float:
    return BORE_VIEW_CENTER[1] - bore_view_crop_radius(teeth) - KEYED_BORE_VIEW_LABEL_DROP


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


# A's boundary stands this far outside the keyway's corners on paper, inside
# the web: at .8 mm T030's letter (3:1) would not fit the web between that
# ring and the root envelope.
KEYED_BORE_DETAIL_MARGIN = 0.0006
# The letters print at the notes' height: at the default 3.5 mm, A's would
# not fit the narrowest web between its boundary and the root envelope.
DETAIL_LETTER_HEIGHT = 0.0025
# Letter centre beyond its boundary: half the letter's ~2.6 mm diagonal
# extent plus ~1 mm of air.
DETAIL_LETTER_REACH = 0.0025
# A's letter stands down and right of the bore, the one diagonal no front-
# view line takes: the centre mark runs square, the root envelope's
# near-side leader comes in from the upper right, T012's web runs down left
# (WEB_REFERENCE_ANGLE_DEG) and the thickness witnesses run right from the
# 3 o'clock tooth. Where the web is narrower than the letter's reach, the
# letter centres in the web.
BORE_LETTER_ANGLE_DEG = -45.0


def _front_ratio(teeth: int) -> float:
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    return numerator / denominator


def front_details(teeth: int) -> tuple[FrontDetail, ...]:
    """The detail boundaries the sheet's front view carries: DETAIL A on a
    keyed sheet, none on a round-bore one."""
    if not keyed(teeth):
        return ()
    ratio = _front_ratio(teeth)
    bore_radius_mm = bore_reach_mm(teeth) + KEYED_BORE_DETAIL_MARGIN * 1000.0 / ratio
    web_mm = floor_limits_mm(teeth)[0] / 2.0 - bore_radius_mm
    return (
        FrontDetail(
            BORE_DETAIL_LETTER,
            (0.0, 0.0),
            bore_radius_mm,
            BORE_LETTER_ANGLE_DEG,
            min(DETAIL_LETTER_REACH, web_mm * ratio / 2000.0),
        ),
    )


def detail_letter_xy(
    detail: FrontDetail, centre: tuple[float, float], radius: float
) -> tuple[float, float]:
    """Sheet centre of ``detail``'s letter round a boundary drawn at sheet
    ``centre`` with sheet ``radius``."""
    angle = math.radians(detail.letter_angle_deg)
    reach = radius + detail.letter_reach
    return centre[0] + reach * math.cos(angle), centre[1] + reach * math.sin(angle)


def front_detail_on_sheet(
    teeth: int, detail: FrontDetail
) -> tuple[tuple[float, float], float]:
    """Nominal sheet centre and radius of ``detail``'s boundary, the gear axis
    on FRONT_CENTER (the build projects the model points instead)."""
    ratio = _front_ratio(teeth)
    return (
        (
            FRONT_CENTER[0] + detail.centre_mm[0] * ratio / 1000.0,
            FRONT_CENTER[1] + detail.centre_mm[1] * ratio / 1000.0,
        ),
        detail.radius_mm * ratio / 1000.0,
    )


# Sheet width of the face-width text block: the stack's "20-GEAR STACK" row
# is wider than the banded value, 36.0 mm on every sheet of the ENFORCE
# round-3 render. Where the face spans less than the text plus a clearance
# each side, the text crowds its extension lines (#834 machinist review,
# sheets 5-20; ENFORCE round 3, sheets 3-20, with the 29 mm the value alone
# had measured): the text then stands outside, right of the view, on the
# extended dimension line.
FACE_WIDTH_TEXT_WIDTH = 0.036
FACE_WIDTH_TEXT_CLEARANCE = 0.002


def face_width_text_inside(teeth: int) -> bool:
    return (
        2.0 * rendered_half_face_width(teeth)
        >= FACE_WIDTH_TEXT_WIDTH + 2.0 * FACE_WIDTH_TEXT_CLEARANCE
    )


# The face width's block is centred on its point, 12 mm under the side view
# with the value alone (T084, ENFORCE round-1 render: block y 88-99 mm, view
# bottom 104.5 mm). The stack's two lines under the value would raise its top
# ~5 mm, onto the view, so the point drops by as much.
FACE_WIDTH_DROP = 0.017
# The tip diameter goes across the side view, beside the face width (rule 11;
# repeat review of 218c85b6: a leader on the end view). Its extension lines
# leave the front face at the tip radius; the text stands right of the view
# at mid-height, between the arrows, the dimension line through it. The
# block -- SEE NOTE 2 over the value and its band, 31 mm wide on the round-2
# T120 ink -- clears the face by the gap and the iso view by 20 mm or more.
BLANK_DIA_TEXT_HALF_WIDTH = 0.016
BLANK_DIA_TEXT_GAP = 0.004


def right_keep(teeth: int) -> dict[str, tuple[float, float]]:
    blank_dia = (
        RIGHT_CENTER[0]
        + rendered_half_face_width(teeth)
        + BLANK_DIA_TEXT_GAP
        + BLANK_DIA_TEXT_HALF_WIDTH,
        RIGHT_CENTER[1],
    )
    y = RIGHT_CENTER[1] - rendered_half_od(teeth) - FACE_WIDTH_DROP
    if face_width_text_inside(teeth):
        return {"FaceWidth": (RIGHT_CENTER[0], y), "BlankDia": blank_dia}
    x = (
        RIGHT_CENTER[0]
        + rendered_half_face_width(teeth)
        + FACE_WIDTH_TEXT_CLEARANCE
        + FACE_WIDTH_TEXT_WIDTH / 2.0
    )
    return {"FaceWidth": (x, y), "BlankDia": blank_dia}


_TOL_LIMIT = 3  # swTolType_e.swTolLIMIT


def _assert_sheet_bands(
    adapter: Any, annotations: list[Any], configuration: str, teeth: int
) -> None:
    """Prove the sheet's gap-floor, blank and tooth-thickness dimensions carry
    THIS configuration's bands.

    One model dimension holds twenty LIMIT bands; the imported display
    dimension reads the band of its view's referenced configuration from the
    saved part, so this is the per-configuration readback after save and
    reopen.
    """
    floor = [a for a in annotations if dimension_name(adapter, a) == "FloorDia"]
    if len(floor) != 1:
        raise RuntimeError(
            f"{configuration}: expected one FloorDia on the sheet, found {len(floor)}"
        )
    display = _early_bound(
        _early_bound(floor[0], "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    kind = int(tolerance.Type)
    observed = (
        float(tolerance.GetMinValue()) * 1000.0,
        float(tolerance.GetMaxValue()) * 1000.0,
    )
    expected = gap_floor_deviations_mm(teeth)
    drifted = any(abs(o - e) > 1e-6 for o, e in zip(observed, expected))
    if kind != _TOL_LIMIT or drifted:
        raise RuntimeError(
            f"{configuration}: sheet FloorDia reads type {kind} {observed} mm, "
            f"expected LIMIT {expected} mm ({floor_limits_mm(teeth)})"
        )
    _telemetry.success(
        f"{configuration}: sheet gap-floor limits {floor_limits_mm(teeth)} mm"
    )
    # Every sheet reads its own blank and tooth-thickness bands back.
    for name, band in (
        ("BlankDia", blank_dia_band(teeth)),
        ("ToothThickness", tooth_thickness_band(teeth)),
    ):
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(
                f"{configuration}: expected one {name} on the sheet, found {len(matches)}"
            )
        display = _early_bound(
            _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        tolerance = _early_bound(
            _early_bound(display.GetDimension2(0), "IDimension").Tolerance,
            "IDimensionTolerance",
        )
        observed = (
            float(tolerance.GetMinValue()) * 1000.0,
            float(tolerance.GetMaxValue()) * 1000.0,
        )
        expected = deviations(band)
        if any(abs(o - e) > 1e-6 for o, e in zip(observed, expected)):
            raise RuntimeError(
                f"{configuration}: sheet {name} reads {observed} mm, expected {expected} mm"
            )
    _telemetry.success(
        f"{configuration}: sheet blank {blank_dia_band(teeth)} and tooth-thickness "
        f"{tooth_thickness_band(teeth)} bands"
    )


def _configure_views(
    adapter: Any, configuration: str, views: tuple[Any, ...]
) -> None:
    """Select one source configuration and verify every view's exact readback."""
    bound_views = tuple(_early_bound(view, "IView") for view in views)
    for view in bound_views:
        view.ReferencedConfiguration = configuration
    # The common drawing chokepoint deliberately does not treat EditRebuild3's
    # BOOL as the sole health signal.  Exact configuration readback is followed
    # by model-dimension import and configuration-qualified native bore-edge
    # validation below.  IView.GetOutline cannot validate nominal geometry: the
    # adapter contract records that SolidWorks pads that box with whitespace.
    rebuild_drawing(adapter, label=f"{configuration} view configuration")
    for view in bound_views:
        observed = str(view.ReferencedConfiguration)
        if observed != configuration:
            raise RuntimeError(
                f"view configuration readback {observed!r} != {configuration!r}"
            )


def _hide_tangent_edges(view: Any, configuration: str) -> None:
    """Drop the end view's tangent edges, and prove they went.

    ENFORCE round 4 of #971: a grey circle at the root radius crossed every
    tooth base, an edge between smooth faces that reads as a hub step or a
    reference circle (draw_dt_crank_drive_gear does the same).
    """
    view.SetDisplayTangentEdges2(0)  # swTangentEdgesHidden
    if int(view.GetDisplayTangentEdges2()) != 0:
        raise RuntimeError(f"failed to hide the {configuration} front view's tangent edges")
    view.UpdateViewDisplayGeometry()


def _assert_tooth_geometry(front: Any, configuration: str, teeth: int) -> None:
    """Prove the view exposes patterned body edges, not a smooth bored blank."""
    edge_count = len(
        visible_view_entities(
            front, 1, label=f"{configuration} front tooth topology"
        )
    )
    minimum = 2 * teeth + 2
    if edge_count < minimum:
        raise RuntimeError(
            f"{configuration} front view exposes {edge_count} model-body edges; "
            f"expected at least {minimum} for {teeth} visible teeth"
        )
    _telemetry.success(
        f"{configuration} drawing tooth topology: {edge_count} visible body edges"
    )


def _activate_view(adapter: Any, view: Any, *, label: str) -> str:
    """Make ``view`` the active view (sketch entities and notes land in it)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _center_bore_view(adapter: Any, view: Any, configuration: str) -> None:
    """Move the configured bore view so the bore axis lands on BORE_VIEW_CENTER."""
    view = _early_bound(view, "IView")
    label = f"{configuration} bore view axis"
    axis = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=label)
    position = tuple(float(value) for value in view.Position)
    target = [position[i] + BORE_VIEW_CENTER[i] - axis[i] for i in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to move the {configuration} bore view")
    rebuild_drawing(adapter, label=f"{configuration} place bore view")
    axis = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=label)
    if math.dist(axis, BORE_VIEW_CENTER) > BORE_VIEW_POSITION_TOL_M:
        raise RuntimeError(
            f"{configuration} bore axis sits at {axis!r}, not {BORE_VIEW_CENTER!r}"
        )


def _sketch_view_circle(
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
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
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


def _crop_bore_view(
    adapter: Any, view: Any, configuration: str, teeth: int, kept: set[str]
) -> None:
    """Crop to a native circle round the bore, read back its outline and
    dimensions; it prints no crop outline (BORE_VIEW_CROP_MARGIN)."""
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    label = f"{configuration} bore view"
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = _activate_view(adapter, view, label=label)
    _sketch_view_circle(
        adapter,
        view,
        BORE_VIEW_CENTER,
        bore_view_crop_radius(teeth),
        add_to_db=False,
        label=f"{label} crop",
    )
    status = int(view.Crop2(False, True, 1))
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"{label} crop")
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    after = {
        dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
        for annotation in (view.GetAnnotations() or ())
    }
    _telemetry.info(
        f"{label} {name!r}: Crop2 status {status}, IsCropped {cropped}, outline "
        f"{tuple(round(value * 1000, 1) for value in outline)} mm, uncropped "
        f"{tuple(round(value * 1000, 1) for value in uncropped)} mm, "
        f"dimensions {sorted(item for item in after if item)}",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"{label} is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[2] - outline[0] >= uncropped[2] - uncropped[0]
    ):
        raise RuntimeError(
            f"{label} crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    # The jagged-outline accessor is invalid without an outline
    # (_drawing_detail_crop), so only the no-outline flag is read back.
    if not bool(view.CropViewNoOutline):
        raise RuntimeError(f"{label}'s crop prints an outline; expected none")
    lost = sorted(kept - after)
    if lost:
        raise RuntimeError(f"{label} lost {lost} to its crop; it holds {sorted(after)}")


# swDimensionTextParts_e: the callout lanes set_dimension_callouts writes.
_CALLOUT_ABOVE = 3
_CALLOUT_BELOW = 4

# One sheet's printed callouts: (sheet, its curated annotations, below-text
# by dimension name, above-text by dimension name).
SheetCallouts = tuple[str, list[Any], dict[str, str], dict[str, str]]


def _rewrite_callouts(adapter: Any, sheets: list[SheetCallouts]) -> None:
    """Write every sheet's callouts again once the last sheet is imported.

    A model dimension's callout text is one value shared by every sheet that
    prints it (OffsetText, DIMENSION_CALLOUTS["ToothThickness"]). Each sheet's
    side view imports the whole marked set (``_curate_repeated_dimensions``),
    which brings in, and deletes, every marked dimension live in its
    configuration: since the T120 marking fix that includes the round bore's
    on T030..T120 and the web's on every sheet, so the keyed sheets reset the
    callouts T012..T024 had written (farm proof 6fda5a4: the reamed bore's Ø
    printed bare, the T012 web without its words).
    """
    for _sheet, printed, below, above in sheets:
        set_dimension_callouts(adapter, printed, below)
        set_dimension_callouts(adapter, printed, above, location="above")


def _assert_settled_callouts(adapter: Any, sheets: list[SheetCallouts]) -> None:
    """After finalize's settling rebuild, every sheet's printed dimensions
    still carry their callouts (``_rewrite_callouts``)."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    faults = []
    for sheet, printed, below, above in sheets:
        if not ddoc.ActivateSheet(sheet):
            raise RuntimeError(f"failed to activate {sheet} for its settled callouts")
        expected = {
            (name, part): text
            for part, texts in ((_CALLOUT_BELOW, below), (_CALLOUT_ABOVE, above))
            for name, text in texts.items()
        }
        for annotation in printed:
            annotation = _early_bound(annotation, "IAnnotation")
            name = dimension_name(adapter, annotation)
            display = None
            for part in (_CALLOUT_BELOW, _CALLOUT_ABOVE):
                text = expected.pop((name, part), None)
                if text is None:
                    continue
                if display is None:
                    display = _early_bound(
                        annotation.GetSpecificAnnotation(), "IDisplayDimension"
                    )
                read = str(display.GetText(part) or "").replace("\r", "")
                if read != text:
                    faults.append(f"{sheet} {name}: {read!r}, expected {text!r}")
        faults.extend(f"{sheet} {name}: not on the sheet" for name, _part in expected)
    if faults:
        raise RuntimeError(
            "dimension callouts after the settling rebuild:\n" + "\n".join(faults)
        )



def _clock_arcs(display: Any) -> list[tuple[tuple[float, float], list[tuple[float, float]]]]:
    """The clock dimension's drawn arcs as (centre, tessellated points), in
    sheet metres, read the way the layout audit reads them."""
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    arcs = []
    for index in range(int(data.GetArcCount())):
        raw = tuple(float(value) for value in (data.GetArcAtIndex2(index) or ()))
        segments = arc_segments(raw)
        if not segments:
            continue
        points = [(segments[0].x0, segments[0].y0), *((s.x1, s.y1) for s in segments)]
        arcs.append(((raw[10], raw[11]), points))
    return arcs


def _sweep_clock_right_of_flat(
    adapter: Any, view: Any, annotations: list[Any], teeth: int, *, label: str
) -> Any:
    """Flip the imported flat clock until its arc sweeps only the quadrant
    right of the flat and above the axis, then re-seat its text there.

    The flips act on the selected dimension (the API's own example selects
    it first), so each one runs with the clock alone selected in its active
    view. Every flip is read back from the drawn arcs and the measured value;
    a clock that ends anywhere else raises with the stray points.
    """
    clock_name = clock_dimension_name(teeth)
    clocks = [
        _early_bound(annotation, "IAnnotation")
        for annotation in annotations
        if dimension_name(adapter, _early_bound(annotation, "IAnnotation")) == clock_name
    ]
    if len(clocks) != 1:
        raise RuntimeError(f"{label}: expected one {clock_name}, found {len(clocks)}")
    annotation = clocks[0]
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    display.ArrowSide = ARROWS_INSIDE
    if int(display.ArrowSide) != ARROWS_INSIDE:
        raise RuntimeError(f"{label}: the flat clock did not keep its arrows inside")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name:
        raise RuntimeError(f"{label}: the flat clock has no selection name")
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    vertex = bore_clock_vertex(teeth)
    text_xy = bore_view_keep(teeth)[clock_name]
    imported = float(_read_member(dimension, "SystemValue"))
    flips: list[str] = []
    stray: list[tuple[float, float]] = []
    for flip in ("", *CLOCK_FLIPS):
        if flip:
            if not drawing.ActivateView(view.GetName2()):
                raise RuntimeError(f"{label}: failed to activate the bore view")
            model.ClearSelection2(True)
            if not model.Extension.SelectByID2(
                selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
            ):
                raise RuntimeError(f"{label}: failed to select the flat clock {selection_name!r}")
            flipped = getattr(display, flip)()
            model.ClearSelection2(True)
            if not flipped:
                raise RuntimeError(f"{label}: {flip} refused on the flat clock")
            flips.append(flip)
            if not annotation.SetPosition2(*text_xy, 0.0):
                raise RuntimeError(f"{label}: failed to re-seat the flat clock text")
            rebuild_drawing(adapter, label=f"{label} clock {flip}")
        arcs = _clock_arcs(display)
        if not arcs:
            raise RuntimeError(f"{label}: the flat clock draws no arc")
        for centre, points in arcs:
            if math.dist(centre, vertex) > CLOCK_ARC_CENTRE_TOL:
                raise RuntimeError(
                    f"{label}: flat clock arc centred at "
                    f"{tuple(round(v * 1000, 2) for v in centre)} mm, not the "
                    f"flat/axis crossing {tuple(round(v * 1000, 2) for v in vertex)} mm"
                )
        stray = [
            point
            for _centre, points in arcs
            for point in points
            if point[0] < vertex[0] - CLOCK_ARC_OVERRUN or point[1] < vertex[1] - CLOCK_ARC_OVERRUN
        ]
        radii = sorted({round(math.dist(centre, points[0]) * 1000, 2) for centre, points in arcs})
        spans = [
            tuple(
                round(math.degrees(math.atan2(y - vertex[1], x - vertex[0])), 1)
                for x, y in (points[0], points[-1])
            )
            for _centre, points in arcs
        ]
        measured = float(_read_member(dimension, "SystemValue"))
        _telemetry.info(
            f"{label}: flat clock after {flips or ['import']}: reads "
            f"{math.degrees(measured):.4f} deg, {len(arcs)} arc(s) spanning {spans} "
            f"deg about the flat/axis crossing, radius {radii} mm, {len(stray)} "
            "point(s) outside the quadrant right of the flat and above the axis",
            clock_flips=len(flips),
            clock_stray_points=len(stray),
            clock_measured_deg=math.degrees(measured),
        )
        if abs(measured - imported) > 1e-9:
            raise RuntimeError(
                f"{label}: {flips[-1]} changed the clock from "
                f"{math.degrees(imported):.4f} to {math.degrees(measured):.4f} deg"
            )
        if not stray:
            if int(display.ArrowSide) != ARROWS_INSIDE:
                raise RuntimeError(f"{label}: {flips} put the clock's arrows outside")
            return display
    raise RuntimeError(
        f"{label}: flat clock arc still leaves the quadrant right of the flat and "
        f"above the axis after {flips}; first stray points "
        f"{[tuple(round(v * 1000, 1) for v in p) for p in stray[:3]]} mm"
    )


def _shelve_tooth_thickness(
    adapter: Any, annotations: list[Any], teeth: int, *, label: str
) -> None:
    """Offset the thickness text onto its own shelf (``tooth_thickness_shelf``)
    and prove the shelf landed there while the line stayed at the tooth.

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
    line_x = front_keep(teeth)["ToothThickness"][0]
    target = tooth_thickness_shelf(teeth)
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
        f"{[round(x * 1000, 2) for x in stations]} mm, line anchor {line_x * 1000:.2f}",
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
            f"{[round(x * 1000, 2) for x in stations]} mm, anchor {line_x * 1000:.2f}"
        )


# The thickness callout's printed rows other than the value, top down.
TOOTH_THICKNESS_ROWS = (
    CALLOUTS_ABOVE["ToothThickness"],
    *DIMENSION_CALLOUTS["ToothThickness"].splitlines(),
)


# How far round the callout's text block a line is still measured; anything
# farther is reported at this distance.
_TEXT_AIR_WINDOW = 0.010


def tooth_thickness_text_air(page: PageInk, teeth: int) -> tuple[float, str]:
    """The smallest printed air between the thickness callout's glyphs and
    any line on ``page`` other than the shelf the text stands on, with the
    nearest line.

    The callout is its printed rows (one PDF text run each) and every run
    inside their joint box (the value and its tolerance). Its name over the
    value prints once a page; its "SEE NOTE 2" flag also prints on the tip
    diameter and on the root envelope (whose block stands just above this
    one), so the flag is the nearest such run under the name. Its shelf is
    the horizontal line under that box spanning it. Air is the glyph-box to
    line distance less half the stroke width.
    """
    def printed(row: str) -> list[Any]:
        key = "".join(row.split())
        return [span for span in page.spans if "".join(span.text.split()) == key]

    name_row, *lower_rows = TOOTH_THICKNESS_ROWS
    names = printed(name_row)
    if len(names) != 1:
        alike = [span.text for span in page.spans if span.text[:6] == name_row[:6]]
        raise ValueError(
            f"T{teeth:03d}: thickness row {name_row!r} printed {len(names)} times "
            f"(runs starting alike: {alike})"
        )
    name = names[0]
    name_x = (name.xmin + name.xmax) / 2.0
    runs = [name]
    for row in lower_rows:
        found = [span for span in printed(row) if span.ymax <= name.ymin]
        if not found:
            raise ValueError(
                f"T{teeth:03d}: thickness row {row!r} printed 0 times under {name_row!r}"
            )
        runs.append(min(
            found,
            key=lambda span: math.hypot((span.xmin + span.xmax) / 2.0 - name_x, name.ymin - span.ymax),
        ))
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
            f"T{teeth:03d}: no shelf under the thickness text {block.format_mm()}"
        )
    return air, nearest


def assert_tooth_thickness_text_air(pdf: Path) -> None:
    """Refuse the export when any line comes nearer the thickness callout's
    text than ``TOOTH_THICKNESS_TEXT_AIR`` on any gear sheet (the printed
    ink, as the machinist reads it)."""
    pages = read_pdf_ink(Path(pdf))
    if len(pages) != len(SHEET_NAMES):
        raise RuntimeError(
            f"{pdf} prints {len(pages)} pages, expected {len(SHEET_NAMES)}"
        )
    airs = {}
    faults = []
    for name, teeth, page in zip(SHEET_NAMES, CONFIGURATION_TEETH, pages):
        air, nearest = tooth_thickness_text_air(page, teeth)
        airs[name] = round(air * 1000, 2)
        if air < TOOTH_THICKNESS_TEXT_AIR:
            faults.append(f"{name}: {nearest}")
    _telemetry.info(f"thickness text air by sheet (mm): {airs}")
    if faults:
        raise RuntimeError(
            f"a line strikes the thickness text (under "
            f"{TOOTH_THICKNESS_TEXT_AIR * 1000:.1f} mm of air):\n" + "\n".join(faults)
        )


def _check_exported_pdf(phase: str) -> None:
    if phase == "after_pdf_save":
        assert_tooth_thickness_text_air(PDF)


# The front view's bore centre mark draws its lines (machinist review of the
# C1-keyed sheets, rule 10: the clock's reference, the tooth centreline, was
# drawn nowhere). Its +X line runs from the bore's rim through the phase-0
# tooth, which the keyway is clocked to, to CENTRE_LINE_OVERRUN past
# the tip, stopping CENTRE_LINE_DIMENSION_AIR short of the thickness
# dimension's line: that line's midpoint, on the bore axis, starts the leader
# to the thickness text's shelf, whose block straddles the axis 6.5 mm on.
# The template already draws every line CENTRE_MARK_LINE_BASE_MM (model) past
# the rim (the r3 print, every sheet 2.49-2.54 mm at its own scale), and
# ICenterMark.SetExtendedLength adds its model length to that (PR 1's r4: its
# T006 sheet asked 1.948 mm and printed the line to rim + (2.5 + 1.948) x 8,
# 0.81 mm under the C of CIRCULAR). Where the base already passes the tip
# the line keeps the template's length. swCenterMarkHandle_e Right 3
# (draw_ch_rocker_strap); the other arms keep the template's.
CENTRE_LINE_OVERRUN = 0.0015
CENTRE_LINE_DIMENSION_AIR = ARROW_TEXT_CLEARANCE
CENTRE_MARK_LINE_BASE_MM = 2.5
_CENTER_MARK_HANDLE_RIGHT = 3


def front_centre_line_end_x(teeth: int) -> float:
    """Sheet x where the front view's +X centre-mark line ends."""
    ratio = _front_ratio(teeth)
    rim = FRONT_CENTER[0] + bore_dia_mm(teeth) * ratio / 2000.0
    base = rim + CENTRE_MARK_LINE_BASE_MM * ratio / 1000.0
    target = min(
        FRONT_CENTER[0] + rendered_half_od(teeth) + CENTRE_LINE_OVERRUN,
        front_keep(teeth)["ToothThickness"][0] - CENTRE_LINE_DIMENSION_AIR,
    )
    return max(base, target)


def front_centre_mark_arms_mm(teeth: int) -> dict[int, float]:
    """SetExtendedLength's model lengths for the front view's centre mark:
    the +X line's extension past the template's, none where that suffices."""
    ratio = _front_ratio(teeth)
    rim = FRONT_CENTER[0] + bore_dia_mm(teeth) * ratio / 2000.0
    extension = (front_centre_line_end_x(teeth) - rim) * 1000.0 / ratio
    extension -= CENTRE_MARK_LINE_BASE_MM
    if extension <= 1e-9:
        return {}
    return {_CENTER_MARK_HANDLE_RIGHT: extension}


def _center_mark_bore(
    adapter: Any,
    view: Any,
    teeth: int,
    *,
    label: str,
    arms_mm: dict[int, float] | None = None,
) -> None:
    """Centre-mark the bore on its arc.  ``IView.AutoInsertCenterMarks2``
    looks for round holes; the keyed bore is an arc and a keyway, so the arc's
    -X point is picked and marked directly (the draw_channel_lever R3 recipe),
    the round bore's alike. ``arms_mm`` extends the mark's lines by
    handle, each that model length past the template's
    (front_centre_mark_arms_mm); empty or None keeps the template's."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    _activate_view(adapter, view, label=label)
    pick = model_point_in_view(
        adapter,
        view,
        (-bore_dia_mm(teeth) / 2000.0, 0.0, 0.0),
        label=f"{label} bore arc -X point",
    )
    extension = _early_bound(draw.Extension, "IModelDocExtension")
    if not extension.SelectByID2(
        "", "EDGE", pick[0], pick[1], 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"failed to select the {label} bore arc")
    mark = ddoc.InsertCenterMark3(CENTER_MARK_SINGLE, False, False)
    draw.ClearSelection2(True)
    if mark is None:
        raise RuntimeError(f"failed to centre-mark the {label} bore")
    if not arms_mm:
        return
    mark = _early_bound(mark, "ICenterMark")
    mark.UseDocDisplaySettings = False
    mark.ShowLines = True
    for handle, arm_mm in arms_mm.items():
        if not mark.SetExtendedLength(0, handle, arm_mm / 1000.0):
            raise RuntimeError(f"{label} centre mark arm {handle} did not extend")
    if bool(mark.UseDocDisplaySettings) or not bool(mark.ShowLines):
        raise RuntimeError(f"{label} centre mark lost its extended lines")
    _telemetry.info(
        f"{label} centre mark line extensions past the template's (model mm): "
        + ", ".join(
            f"{handle}={float(mark.GetExtendedLength(0, handle)) * 1000.0:.3f}"
            for handle in range(4)
        )
    )


def _note_box(note: Any, *, label: str) -> tuple[float, float, float, float]:
    """``INote.GetExtent``'s lower-left and upper-right corners, sheet metres."""
    values = tuple(float(value) for value in (note.GetExtent() or ()))
    if len(values) != 6 or not all(map(math.isfinite, values)):
        raise RuntimeError(f"{label}: invalid note extent {values!r}")
    box = (values[0], values[1], values[3], values[4])
    if box[0] >= box[2] or box[1] >= box[3]:
        raise RuntimeError(f"{label}: empty note extent {values!r}")
    return box


def _set_note_height(note: Any, height: float, *, label: str) -> None:
    """Set a note's character height (add_property_linked_note's form)."""
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label}: note has no text format")
    text_format.CharHeight = float(height)
    if annotation.SetTextFormat(0, False, text_format) is not True:
        raise RuntimeError(f"{label}: failed to set the note's text height")


def _centred_view_note(
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
    _activate_view(adapter, view, label=label)
    raw = add_note(adapter, text, center_x, top if top is not None else center_y)
    if raw is None:
        raise RuntimeError(f"failed to add the {label} note")
    note = _early_bound(raw, "INote")
    if height is not None:
        _set_note_height(note, height, label=label)
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")

    def error_of(box: tuple[float, float, float, float]) -> tuple[float, float]:
        if top is not None:
            return (box[0] + box[2]) / 2.0 - center_x, box[3] - top
        return (box[0] + box[2]) / 2.0 - center_x, (box[1] + box[3]) / 2.0 - center_y

    for _ in range(2):
        error = error_of(_note_box(note, label=label))
        if max(abs(error[0]), abs(error[1])) <= NOTE_CENTRING_TOL_M / 10.0:
            break
        position = tuple(float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(position[0] - error[0], position[1] - error[1], 0.0):
            raise RuntimeError(f"failed to centre the {label} note")
        rebuild_drawing(adapter, label=f"{label} note")
    error = error_of(_note_box(note, label=label))
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


def _label_bore_view(adapter: Any, view: Any, teeth: int, *, label: str) -> None:
    """Title the bore view DETAIL A under its crop circle: a note the view
    owns, centred on the bore axis by its extent, its top edge on
    ``bore_view_label_top``."""
    _centred_view_note(
        adapter,
        view,
        bore_view_label(teeth),
        center_x=BORE_VIEW_CENTER[0],
        top=bore_view_label_top(teeth),
        label=f"{label} title",
    )


def _mark_front_details(adapter: Any, front: Any, teeth: int, *, label: str) -> None:
    """Draw each of the sheet's detail boundaries on the front view (a plain
    view-sketch circle in the outline's black, draw_ch_amplitude_bar's
    detail mark) and letter it outside, both owned by the view."""
    for detail in front_details(teeth):
        detail_label = f"{label} detail {detail.letter}"
        _activate_view(adapter, front, label=detail_label)
        x_mm, y_mm = detail.centre_mm
        centre, rim = (
            model_point_in_view(
                adapter, front, (x / 1000.0, y_mm / 1000.0, 0.0), label=f"{detail_label} {name}"
            )
            for x, name in ((x_mm, "centre"), (x_mm + detail.radius_mm, "rim"))
        )
        radius = math.dist(centre, rim)
        circle = _sketch_view_circle(
            adapter, front, centre, radius, add_to_db=True, label=f"{detail_label} boundary"
        )
        segment = _early_bound(circle, "ISketchSegment")
        segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
        if int(segment.Color) != 0:
            raise RuntimeError(f"{detail_label} boundary colour did not persist")
        adapter.currentModel.ClearSelection2(True)
        rebuild_drawing(adapter, label=f"{detail_label} boundary")
        letter_x, letter_y = detail_letter_xy(detail, centre, radius)
        _centred_view_note(
            adapter,
            front,
            detail.letter,
            center_x=letter_x,
            center_y=letter_y,
            height=DETAIL_LETTER_HEIGHT,
            label=f"{detail_label} letter",
        )
        _telemetry.info(
            f"{detail_label}: boundary at ({centre[0] * 1000:.2f}, {centre[1] * 1000:.2f}) mm, "
            f"radius {radius * 1000:.2f} mm; letter at ({letter_x * 1000:.2f}, "
            f"{letter_y * 1000:.2f}) mm"
        )


def _curate_repeated_dimensions(
    adapter: Any,
    view: Any,
    *,
    keep: dict[str, tuple[float, float]],
    view_label: str,
) -> list[Any]:
    """Import a complete sheet's model dimensions, allowing cross-sheet copies.

    ``InsertModelAnnotations3``'s ``DuplicateDims`` flag means *eliminate*
    duplicates when true.  The standard curator uses true because ordinary
    drawings place each model dimension once.  This configured-family package
    must print the same driving dimensions on all twenty standalone sheets, so
    it deliberately passes false and then curates only the returned objects.
    """
    declared = set().union(*DRAWING_DIMENSIONS.values())
    unknown = sorted(set(keep) - declared)
    if unknown:
        raise RuntimeError(f"{view_label} keeps undeclared dimensions: {unknown}")

    drawing = _early_bound(adapter.currentModel, "IModelDoc2")
    ddoc = _early_bound(drawing, "IDrawingDoc")
    name = view_name(adapter, view)
    if not bool(ddoc.ActivateView(name)):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    drawing.ClearSelection2(True)
    extension = _early_bound(drawing.Extension, "IModelDocExtension")
    if not bool(
        extension.SelectByID2(
            name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
        )
    ):
        raise RuntimeError(f"failed to select drawing view {name!r}")
    result = adapter._attempt(
        lambda: ddoc.InsertModelAnnotations3(
            0,  # swImportModelItemsFromEntireModel
            _INSERT_DIMS_MARKED,
            False,  # selected view only
            False,  # allow the same model dimensions on every package sheet
            True,  # include dimensions on construction/hidden features
            False,
        ),
        default=None,
    )
    drawing.ClearSelection2(True)
    if not result or isinstance(result, str):
        raise RuntimeError(f"{view_label} imported no marked model dimensions")
    annotations = delete_unnamed_imports(adapter, list(result))
    names = {dimension_name(adapter, annotation) for annotation in annotations}
    delete = tuple(sorted(name for name in names if name and name not in keep))
    curated = curate_dimensions(
        adapter, annotations, delete=delete, reposition=dict(keep)
    )
    present = {dimension_name(adapter, annotation) for annotation in curated}
    missing = sorted(set(keep) - present)
    if missing:
        raise RuntimeError(
            f"{view_label} is missing model dimensions {missing}; "
            f"available={sorted(present)}"
        )
    return curate_dimensions(adapter, curated, reposition=dict(keep))


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-gear source", await adapter.open_model(str(SOURCE)))
    await assert_saved_configuration_topology(adapter, phase="drawing source")
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("dt-cone-gear"),
    )
    _assert_dimension_arrow_length(drawing_model)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="cone-gear batch")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Gear Batch Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone gear; configured T012 through T120 by six",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    sheet_callouts: list[SheetCallouts] = []
    for teeth in CONFIGURATION_TEETH:
        configuration = f"T{teeth:03d}"
        view_scale = SHEET_SCALES[configuration]
        if not ddoc.ActivateSheet(configuration):
            raise RuntimeError(f"failed to activate cone-gear sheet {configuration}")

        front = place_view(
            adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=view_scale
        )
        right = place_view(
            adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=view_scale
        )
        iso = place_view(
            adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=view_scale
        )
        # Only a keyed bore takes its enlarged view (BORE_VIEW_CENTER).
        bore_view = (
            place_view(
                adapter,
                str(SOURCE),
                "*Front",
                *BORE_VIEW_CENTER,
                scale=bore_view_scale(teeth),
            )
            if keyed(teeth)
            else None
        )
        views = tuple(view for view in (front, right, iso, bore_view) if view is not None)
        _configure_views(adapter, configuration, views)
        for view in views:
            set_hidden_lines_removed(adapter, view)
        _hide_tangent_edges(front, configuration)
        _assert_tooth_geometry(front, configuration, teeth)

        # The bore view imports FIRST, while it is uncropped: a model
        # dimension already on the sheet is not imported again, and no other
        # view keeps the bore sketch's dimensions.  The sketch (BoreProfile,
        # or KeyedBoreProfile on T030..T120) is consumed by its cut, so it
        # imports without being shown (_drawing_hidden_sketches r21); a round
        # bore's imports with the front view's.
        bore_annotations: list[Any] = []
        if bore_view is not None:
            _center_bore_view(adapter, bore_view, configuration)
            bore_keep = bore_view_keep(teeth)
            bore_annotations = hidden_sketches.curate_view_dimensions(
                adapter,
                bore_view,
                keep=bore_keep,
                view_label=f"{configuration} bore",
                dimensions_by_feature=DRAWING_DIMENSIONS,
            )
            clock = _sweep_clock_right_of_flat(
                adapter, bore_view, bore_annotations, teeth,
                label=f"{configuration} bore view",
            )
            clocks.append((configuration, clock, teeth))
            _crop_bore_view(adapter, bore_view, configuration, teeth, set(bore_keep))
        # The part saves its authoring sketches hidden; the front view shows
        # the tooth and floor ones again for their dimensions, the side view
        # the tip-diameter witness (the iso view shows the part as saved).
        # The targeted import still delivers the dimensions on every sheet
        # after the first (probe 834-gapfloor-c301).
        front_annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            front,
            keep=front_keep(teeth),
            view_label=f"{configuration} front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        # ENFORCE round 4 of #971: the root envelope's dimension line crossed
        # the centre and the bore; its leader stops on its near rim. Through
        # the centre it also crossed T012's web dimension line (screen of
        # f21dfcdd2ba7, rule 14) and ran through DETAIL A's boundary. A round
        # bore's diameter on the front view stops on its near rim likewise,
        # clear of the centre mark and the web.
        near_side = ("FloorDia",) if keyed(teeth) else ("FloorDia", "BoreCutDia")
        for name in near_side:
            found = [
                item for item in front_annotations
                if dimension_name(adapter, item) == name
            ]
            if len(found) != 1:
                raise RuntimeError(
                    f"{configuration}: expected one {name} dimension, found {len(found)}"
                )
            set_near_side_diameter(found[0], f"{configuration} {name}")
        rebuild_drawing(adapter, label=f"{configuration} near-side diameter leaders")
        # The face width first: the whole-model import deletes whatever it
        # does not keep, the witness's BlankDia included, which the targeted
        # import then brings in with its sketch shown in this view.
        side_keep = right_keep(teeth)
        right_annotations = _curate_repeated_dimensions(
            adapter,
            right,
            keep={"FaceWidth": side_keep["FaceWidth"]},
            view_label=f"{configuration} right",
        )
        right_annotations += hidden_sketches.curate_view_dimensions(
            adapter,
            right,
            keep={"BlankDia": side_keep["BlankDia"]},
            view_label=f"{configuration} side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        _assert_sheet_bands(
            adapter, [*front_annotations, *right_annotations], configuration, teeth
        )
        annotations = [*bore_annotations, *front_annotations, *right_annotations]
        # The sheet's own bore, and RV-03's web on T012 only (front_keep).
        printed = sheet_dimension_names(teeth)
        callouts = {
            name: text for name, text in DIMENSION_CALLOUTS.items() if name in printed
        }
        above = {name: text for name, text in CALLOUTS_ABOVE.items() if name in printed}
        set_dimension_callouts(adapter, annotations, callouts)
        set_dimension_callouts(adapter, annotations, above, location="above")
        sheet_callouts.append((configuration, annotations, callouts, above))
        assert_imported_precision(adapter, annotations, {
            name: places for name, places in DRAWING_PRECISION_BY_NAME.items()
            if name in printed
        })
        _center_mark_bore(
            adapter, front, teeth, label=f"{configuration} front",
            arms_mm=front_centre_mark_arms_mm(teeth),
        )
        if bore_view is not None:
            _center_mark_bore(adapter, bore_view, teeth, label=f"{configuration} bore view")
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        if not sheet.SetScale(*view_scale, False, False):
            raise RuntimeError(f"failed to pin the {configuration} sheet scale")
        _shelve_tooth_thickness(
            adapter, front_annotations, teeth, label=f"{configuration} thickness text"
        )
        _mark_front_details(adapter, front, teeth, label=configuration)
        # Last, as before: the sheet's notes below land while the bore view
        # (the front view on a round-bore sheet) is active.
        if bore_view is not None:
            _label_bore_view(adapter, bore_view, teeth, label=f"{configuration} bore view")
        else:
            _activate_view(adapter, front, label=f"{configuration} notes")

        add_property_linked_note(
            adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025
        )
        numbered = add_note(adapter, sheet_notes(teeth), *NUMBERED_NOTES_POS)
        if numbered is None:
            raise RuntimeError(f"failed to add the {configuration} numbered notes")
        _set_note_height(numbered, 0.0025, label=f"{configuration} numbered notes")
        rebuild_drawing(adapter, label=f"{configuration} layout audit")
        check_drawing_layout(
            adapter, layout=SPEC.layout, stem=f"cone-gear {configuration}"
        )

    _rewrite_callouts(adapter, sheet_callouts)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Gear Batch Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales=SHEET_SCALES,
        settled_checks=(lambda: _assert_settled_callouts(adapter, sheet_callouts),),
        checkpoint=_check_exported_pdf,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
