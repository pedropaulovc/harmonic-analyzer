r"""Create the complete cone-gear batch drawing package (MHA-DT-03).

Every configured family member T012..T120 by six receives a standalone sheet
(T006 is MHA-DT-37, draw_dt_cone_tip_gear).  Each sheet selects its own part
configuration, imports the native model-owned blank diameter, bore (T012..T024
a round reamed bore: its diameter; T030..T120 round with a hub keyway:
diameter, keyway width and T), face width, driving
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
import _cone_gear_sheet as cone_sheet
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import _INSERT_DIMS_MARKED, delete_unnamed_imports
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
)
from _drawing_edges import visible_view_entities
import _drawing_hidden_sketches as hidden_sketches
from _drawing_layout_collect import check_drawing_layout
from _drawing_leaders import (
    ARROW_TEXT_CLEARANCE,
    set_near_side_diameter,
)
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _fit_deviations import deviations
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _pdf_ink import read_pdf_ink
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
# x 0.246: the #1038 face (7.4528) is 0.58 mm wider each side at T084's 2:1,
# and the thickness shelf keeps its 3 mm off the view's left edge there.
RIGHT_CENTER = (0.246, FRONT_CENTER[1])
ISO_CENTER = (0.355, 0.150)
# The keyed bore (T030..T120) prints in its own enlarged view: a *Front model
# view of the sheet's configuration, cropped by a circle round the bore (the
# MHA-DT-VN-61 pattern of draw_amplitude_bar and draw_pinion_arbor; their
# native detail views would not take moved or imported dimensions).  The view
# sits lower left, under the front view and left of the thickness callout,
# and carries every keyed-bore dimension: diameter, keyway width and T.
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
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
CENTER_MARK_SINGLE = 2  # swCenterMarkStyle_e.swCenterMark_Single

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
# fit, its mate and its diametral clearance (rule 23: the part sheet prints a
# bond with its clearance); the compound is MHA-DT-00's bonding step's.
SHAFT_MATE = "MHA-DT-04"
# A matched pair names its mate by name and number (rule 4; round-1 review
# of the fan-out: note 1 named MHA-DT-04 by number only, and no land).
SHAFT_NAME = str(_config.parts("dt-cone-gear-shaft")["title"]).upper()
_TIP_GEAR = _config.parts("dt-cone-tip-gear")
TIP_GEAR_MATE = str(_TIP_GEAR["number"]).strip().upper()  # MHA-DT-37
TIP_GEAR_NAME = str(_TIP_GEAR["title"]).upper()
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
    """Note 1 of a round-bored sheet: the bonded slip fit, its mate and its
    diametral clearance at the parts' printed limits (rule 23; machinist
    review, farm run 20261112T075603458Z: the bond gap was printed nowhere)."""
    if teeth in SPIGOT_TEETH:
        mate = f"{TIP_GEAR_NAME} {TIP_GEAR_MATE} SPIGOT"
    else:
        # The land by its diameter, as the keyed sheets name theirs: "LAND 2"
        # was a label no sheet defined (rule 26; machinist review, farm run
        # 20261112T035245975Z).
        land = f"\u00d8{inch_text(bore_dia_mm(teeth), BORE_BAND_PLACES)} LAND"
        mate = f"{SHAFT_NAME} {SHAFT_MATE}, {land}"
    clearance = _inch_limits(*dt_cone_gear_spec.bond_clearance_mm(teeth))
    return f"{BORE_NOTE_NUMBER}. BONDED SLIP FIT ON {mate} (CLEARANCE {clearance} ON \u00d8)."


def sheet_notes(teeth: int) -> str:
    """The sheet's numbered notes, flagged from the bore and teeth callouts.

    Note 1 is the bore's fit (rule 4).  A keyed bore's bands are narrower
    than the shop's turned and milled rows, so it is made to the measured
    land, with the clearance the parts' limits give as REF, and names the
    key its keyway slides on.  A round bore is bonded (owner decision
    2026-11-09, C1 keyed, PR #1992): the note names the fit, its mate and
    its diametral clearance (rule 23).
    Note 2 names the mesh and the fit route of the tip, thickness and root
    bands: over pins, then the feel set at assembly (MHA-DT-00 check 4;
    GEAR DATA carries the backlash as REF, #2586); it
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
        "THEN BY FEEL AT ASSEMBLY,",
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


def floor_dia_y(teeth: int) -> float:
    """Anchor y of the root-envelope stack on ``teeth``'s sheet
    (``cone_sheet.floor_dia_y``): the thickness witness stands half the
    sheet-scale arc thickness above the bore axis."""
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    half_thickness = tooth_thickness_mm(teeth) * numerator / (denominator * 2000.0)
    return cone_sheet.floor_dia_y(
        FRONT_CENTER[1], rendered_half_od(teeth), half_thickness
    )


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
        "FloorDia": (
            FRONT_CENTER[0] + half_od + cone_sheet.FLOOR_DIA_GAP_X,
            floor_dia_y(teeth),
        ),
        # Vertical dimension on the +X tooth: the anchor's x places its
        # line just right of the tip circle. Its y is where the import first
        # hangs the text, below the gear; the text then leaves the line for
        # its own shelf (``cone_sheet.shelve_tooth_thickness``).
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
    """Sheet point where the thickness text's shelf starts on ``teeth``'s
    sheet (``cone_sheet.tooth_thickness_shelf``)."""
    return cone_sheet.tooth_thickness_shelf(
        front_keep(teeth)["ToothThickness"][0], floor_dia_y(teeth)
    )


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
    witness and right of the keyway width's block.  The keyway width's text
    stands right of the circle under the axis.
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
    width_right = x + crop + KEYWAY_WIDTH_TEXT_GAP + 2.0 * KEYWAY_WIDTH_TEXT_HALF_WIDTH
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


# A's boundary stands this far outside the keyway's corners on paper, inside
# the web: at .8 mm T030's letter (3:1) would not fit the web between that
# ring and the root envelope.
KEYED_BORE_DETAIL_MARGIN = 0.0006
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


def front_details(teeth: int) -> tuple[cone_sheet.FrontDetail, ...]:
    """The detail boundaries the sheet's front view carries: DETAIL A on a
    keyed sheet, none on a round-bore one."""
    if not keyed(teeth):
        return ()
    ratio = _front_ratio(teeth)
    bore_radius_mm = bore_reach_mm(teeth) + KEYED_BORE_DETAIL_MARGIN * 1000.0 / ratio
    web_mm = floor_limits_mm(teeth)[0] / 2.0 - bore_radius_mm
    return (
        cone_sheet.FrontDetail(
            BORE_DETAIL_LETTER,
            (0.0, 0.0),
            bore_radius_mm,
            BORE_LETTER_ANGLE_DEG,
            min(cone_sheet.DETAIL_LETTER_REACH, web_mm * ratio / 2000.0),
        ),
    )


def front_detail_on_sheet(
    teeth: int, detail: cone_sheet.FrontDetail
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


def _crop_bore_view(
    adapter: Any, view: Any, configuration: str, teeth: int, kept: set[str]
) -> None:
    """Crop to a native circle round the bore, read back its outline and
    dimensions; it prints no crop outline (BORE_VIEW_CROP_MARGIN)."""
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    label = f"{configuration} bore view"
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = cone_sheet.activate_view(adapter, view, label=label)
    cone_sheet.sketch_view_circle(
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


# The thickness callout's printed rows other than the value, top down.
TOOTH_THICKNESS_ROWS = (
    CALLOUTS_ABOVE["ToothThickness"],
    *DIMENSION_CALLOUTS["ToothThickness"].splitlines(),
)


def assert_tooth_thickness_text_air(pdf: Path) -> None:
    """Refuse the export when any line comes nearer the thickness callout's
    text than ``cone_sheet.TOOTH_THICKNESS_TEXT_AIR`` on any gear sheet (the printed
    ink, as the machinist reads it)."""
    pages = read_pdf_ink(Path(pdf))
    if len(pages) != len(SHEET_NAMES):
        raise RuntimeError(
            f"{pdf} prints {len(pages)} pages, expected {len(SHEET_NAMES)}"
        )
    airs = {}
    faults = []
    for name, page in zip(SHEET_NAMES, pages):
        air, nearest = cone_sheet.tooth_thickness_text_air(
            page, TOOTH_THICKNESS_ROWS, sheet=name
        )
        airs[name] = round(air * 1000, 2)
        if air < cone_sheet.TOOTH_THICKNESS_TEXT_AIR:
            faults.append(f"{name}: {nearest}")
    _telemetry.info(f"thickness text air by sheet (mm): {airs}")
    if faults:
        raise RuntimeError(
            f"a line strikes the thickness text (under "
            f"{cone_sheet.TOOTH_THICKNESS_TEXT_AIR * 1000:.1f} mm of air):\n"
            + "\n".join(faults)
        )


def _check_exported_pdf(phase: str) -> None:
    if phase == "after_pdf_save":
        assert_tooth_thickness_text_air(PDF)


# The front view's bore centre mark draws the clock: its +X line is the
# centreline the keyway (T030..T120) and the phase-0 tooth share, so their 0 deg
# holds to the title block's angle (rule 26: features in line share a drawn
# centreline; error_budget.yaml cone_flat_clock) and no sheet
# dimensions it (machinist review of the C1-keyed sheets, PR 2 round 2: a
# ±.25° clock in DETAIL A named a tooth that view does not draw). The line
# runs from the bore's rim through that tooth to CENTRE_LINE_OVERRUN past
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
    cone_sheet.activate_view(adapter, view, label=label)
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


def _label_bore_view(adapter: Any, view: Any, teeth: int, *, label: str) -> None:
    """Title the bore view DETAIL A under its crop circle: a note the view
    owns, centred on the bore axis by its extent, its top edge on
    ``bore_view_label_top``."""
    cone_sheet.centred_view_note(
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
        cone_sheet.activate_view(adapter, front, label=detail_label)
        x_mm, y_mm = detail.centre_mm
        centre, rim = (
            model_point_in_view(
                adapter, front, (x / 1000.0, y_mm / 1000.0, 0.0), label=f"{detail_label} {name}"
            )
            for x, name in ((x_mm, "centre"), (x_mm + detail.radius_mm, "rim"))
        )
        radius = math.dist(centre, rim)
        circle = cone_sheet.sketch_view_circle(
            adapter, front, centre, radius, add_to_db=True, label=f"{detail_label} boundary"
        )
        segment = _early_bound(circle, "ISketchSegment")
        segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
        if int(segment.Color) != 0:
            raise RuntimeError(f"{detail_label} boundary colour did not persist")
        adapter.currentModel.ClearSelection2(True)
        rebuild_drawing(adapter, label=f"{detail_label} boundary")
        letter_x, letter_y = cone_sheet.detail_letter_xy(detail, centre, radius)
        cone_sheet.centred_view_note(
            adapter,
            front,
            detail.letter,
            center_x=letter_x,
            center_y=letter_y,
            height=cone_sheet.DETAIL_LETTER_HEIGHT,
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
    cone_sheet.assert_dimension_arrow_length(drawing_model)
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
        cone_sheet.shelve_tooth_thickness(
            adapter,
            front_annotations,
            line_x=front_keep(teeth)["ToothThickness"][0],
            target=tooth_thickness_shelf(teeth),
            label=f"{configuration} thickness text",
        )
        _mark_front_details(adapter, front, teeth, label=configuration)
        # Last, as before: the sheet's notes below land while the bore view
        # (the front view on a round-bore sheet) is active.
        if bore_view is not None:
            _label_bore_view(adapter, bore_view, teeth, label=f"{configuration} bore view")
        else:
            cone_sheet.activate_view(adapter, front, label=f"{configuration} notes")

        add_property_linked_note(
            adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025
        )
        numbered = add_note(adapter, sheet_notes(teeth), *NUMBERED_NOTES_POS)
        if numbered is None:
            raise RuntimeError(f"failed to add the {configuration} numbered notes")
        cone_sheet.set_note_height(
            numbered, 0.0025, label=f"{configuration} numbered notes"
        )
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
