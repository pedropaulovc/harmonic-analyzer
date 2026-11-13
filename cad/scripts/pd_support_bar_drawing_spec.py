"""Pure-data drawing contract for the support bar (MHA-PD-07).

Split from ``pd_support_bar_spec`` on purpose: the latch hook, the platen
guide, the transgear hanger joints and the paper-drive assembly import the
bar's geometry from there, so the print's marks, places, callouts and notes
living there would re-key all of them on every print edit. This module is
imported only by the part build (which authors the marks, bands and places on
the model) and its drawing.

Print frame (the build's): the bar runs along X with x = 0 at its centre, its
height along Y with y = 0 at mid-height, and its depth along Z with the FRONT
(platen) face at z = -4.5 and the BACK (hanger) face at z = +4.5.

* The hanger row's stations run from the bar's left end (x = -226 seen on the
  back face) and its height from the TOP face, which carries the platen's top
  rail: the pivot and the latch hook's base place the platen's arm and hook
  relative to it.
* The clamp row's stations run from the same end (x = -226, the sheet's right
  in the front-face view) and its height from the top face. The east pair
  (that end's, -X) are round counterbored holes; the west pair (+X) are
  counterbored slots along the bar that take up the column pitch (owner
  ruling 2026-10-15, option A).
* The platen guide (MHA-PD-11) hangs on the top face and slides along it,
  and the platen's (MHA-PD-02) back slides across the front face: both faces
  carry the slide roughness (``SURFACE_FINISHES``, drawing-guidelines rule 6).

The rows' nominals are the build's (``build_pd_support_bar``), which owns the
bar length and the clamp-screw stations.
"""

from __future__ import annotations

import _config
from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from _column_clamp_interface import BAR_DEPTH
from pd_support_bar_spec import (
    BAR_BAND_PLACES,
    BAR_HEIGHT,
    BRACKET_TAP_SPEC,
    HOLE_POSITION_PLACES,
    PIVOT_TAP_THREAD,
    UNIT,
)

# The clamp holes' row height and stations print .XXX alone: the title
# block's ±.005 (build_pd_support_bar.CLAMP_POSITION_BAND) holds the MHA-SH-02
# back-arc taps' fixed-fastener stack, which the .XX row's ±.01 would overrun.
CLAMP_POSITION_PLACES = 3
# The clamp counterbores' depth prints .XX: under its band the shallowest
# depth still sinks the clamp-screw head below the front face the platen
# slides across (build_pd_support_bar.CLAMP_HEAD_RECESS).
CLAMP_CBORE_DEPTH_PLACES = 2
# Every native Hole Wizard length (the round counterbores' Ø, depth) prints
# .XXX, under the title block's DRILLED HOLES row.
CLAMP_HOLE_CALLOUT_PLACES = 3
# By native Hole Wizard variable: the round counterbores' Ø's and depth.
CLAMP_CALLOUT_PRECISION = {
    "hw-thruholedia": CLAMP_HOLE_CALLOUT_PLACES,
    "hw-cbdia": CLAMP_HOLE_CALLOUT_PLACES,
    "hw-cbdepth": CLAMP_CBORE_DEPTH_PLACES,
}
# The west slots' runs print .XX: at ±.01 the shortest still closes the
# column-pitch stack (build_pd_support_bar.clamp_slot_closure_margin) and the
# longest stays inside the shortest counterbore (clamp_slot_head_clearance),
# so the .XXX grade bought nothing (v49 machinist review). Their width
# carries the drilled holes' +.004/0 at .XXX. Their counterbore width
# carries explicit asymmetric limits: the minimum (.330) clears the head's
# full-float envelope, while the upper deviation stays the ordinary .XX
# band. The round counterbores' head stays coaxial, while a slid head adds
# the slot run's overrun (build_pd_support_bar.clamp_slot_head_clearance),
# so the callout says the minimum is for the slid head (3de09b9 machinist
# review).
CLAMP_SLOT_WIDTH_PLACES = 3
CLAMP_SLOT_PLACES = 2
CLAMP_SLOT_CBORE_WIDTH_PLACES = 3
CLAMP_SLOT_CBORE_WIDTH_LIMITS = (-0.127, 0.254)  # -.005/+.010
HANGER_STATION_NAMES = ("PivotTapStation", "BracketTapStation1", "BracketTapStation2")
# The hook taps' stations print as REF, "(11.459)": the MHA-PD-14 hook is the
# master, and SPOT THRU MHA-PD-14 AT ASSEMBLY on their callout sets their
# position, so a band on them controls nothing (round 3 machinist review of
# the fan-out). The pivot's station and the row height it shares keep the
# ±.002 (HOLE_POSITION_TOL; owner exception RV-01 in pd-support-bar.yaml).
HOOK_TAP_REFERENCE_NAMES = ("BracketTapStation1", "BracketTapStation2")
BANDED_HANGER_NAMES = ("HangerRowHeight", "PivotTapStation")
CLAMP_STATION_NAMES = (
    "ClampStation1",
    "ClampStation2",
    "ClampStation3",
    "ClampStation4",
)
# The clamp row's two runs each read their own .551 from the top face (round
# 7 review blocker: the round pair's east run carried no height): the west
# run's ClampRowHeight off the +X end in VIEW D, the east run's off a stub
# over its end in the principal view, the end's other side crowded in VIEW D
# (the round holes' callout and leader, END A, the 1.010 and the stations).
CLAMP_EAST_HEIGHT_NAME = "ClampEastRowHeight"

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"Length", "Height"},
    "Bar": {"Depth"},
    "HangerRowReference": {"HangerRowHeight", *HANGER_STATION_NAMES},
    "ClampRowReference": {
        "ClampRowHeight",
        CLAMP_EAST_HEIGHT_NAME,
        *CLAMP_STATION_NAMES,
    },
    # The pivot and hook taps print once each, on their countersinks'
    # stacked callouts (below); the tap drill is the TAP size's.
    "CountersinkReference": {"PivotCskDia", "BracketCskDia"},
    "ClampSlotProfile": {"ClampSlotWidth", "ClampSlotTravel"},
    # The counterbore's run is the slot's: one .12 between the shared end
    # centres serves both (machinist review round 2: printed twice).
    "ClampSlotCboreProfile": {"ClampSlotCboreWidth"},
    "ClampSlotCounterbores": {"ClampSlotCboreDepth"},
}

# The bar's two .XXX bands are authored first, by the build's own literal
# (test_pd_guide_lock_fit_drawing pins it); the rest of the print's places
# follow from here.
SHEET_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {"Length": 1},
    "HangerRowReference": {
        "HangerRowHeight": HOLE_POSITION_PLACES,
        **dict.fromkeys(HANGER_STATION_NAMES, HOLE_POSITION_PLACES),
    },
    "ClampRowReference": {
        "ClampRowHeight": CLAMP_POSITION_PLACES,
        CLAMP_EAST_HEIGHT_NAME: CLAMP_POSITION_PLACES,
        **dict.fromkeys(CLAMP_STATION_NAMES, CLAMP_POSITION_PLACES),
    },
    "CountersinkReference": {"PivotCskDia": 3, "BracketCskDia": 3},
    "ClampSlotProfile": {
        "ClampSlotWidth": CLAMP_SLOT_WIDTH_PLACES,
        "ClampSlotTravel": CLAMP_SLOT_PLACES,
    },
    "ClampSlotCboreProfile": {
        "ClampSlotCboreWidth": CLAMP_SLOT_CBORE_WIDTH_PLACES,
    },
    "ClampSlotCounterbores": {"ClampSlotCboreDepth": CLAMP_CBORE_DEPTH_PLACES},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    **SHEET_PRECISION,
    "BarProfile": {**SHEET_PRECISION["BarProfile"], "Height": BAR_BAND_PLACES},
    "Bar": {"Depth": BAR_BAND_PLACES},
}

# The two hole rows stand .020 apart (the taps .571, the clamp holes .551
# under the top face), so one drawn centreline read as both (round 4
# machinist review; rule 26: holes in line share a drawn centreline, holes
# not in line must not). Each row's reference sketch draws its own lines,
# only where its holes are, and no two rows' lines share a stretch of the
# bar (build_pd_support_bar.ROW_CENTRELINES): the taps' one line runs from
# just short of the pivot to HANGER_HEIGHT_X, where the .571 reads off it;
# the clamp holes' east line from END A past the round pair, its own .551
# off its end; its west line from short of the slots to the +X end, where
# the other .551 reads off it. Model
# millimetres along the bar from its centre; each overrun clears the
# widest ring round its end hole (a slot counterbore reaches 5.75).
TAP_CENTRELINE_OVERRUN = 6.0
CLAMP_CENTRELINE_OVERRUN = 8.0
HANGER_HEIGHT_X = 120.0

# Rule 7: a location dimension and an overall or stock size carry their value
# and band alone; the mate a hole's location serves stands once, on that
# hole's size callout, and a callout carries at most two lines of words.
DIMENSION_CALLOUTS = {
    # The height and thickness print .XXX for the stacks they set, so each
    # names its stack (rule 4: "a width that sets a stack names the stack";
    # round 4 machinist review): the bottom rail's running clearance under the
    # bar and the MHA-PD-12 lock's overlap of it
    # (build_pd_paper_drive_assembly._assert_lock_retention), and the
    # MHA-PD-VN-57 pivot screw's thread engagement, which at .XX falls under
    # rule 18's 1.5D at the thinnest bar (transgear_hanger_joints).  Keeping
    # both bands leaves pd_support_bar_spec, and every part importing it,
    # unkeyed.
    # Two short lines each: the height's text stands right of the round
    # counterbores' callout (draw_pd_support_bar.BACK_KEEP); the thickness's
    # left of section A-A's left extension line (a 28-character row ran
    # through it, round 7 of the fan-out; draw_pd_support_bar.SECTION_KEEP).
    "Height": "SETS MHA-PD-12\nRETENTION",
    "Depth": "SETS MHA-PD-VN-57\nENGAGEMENT",
    # One stacked callout per hole or pattern, on its countersink's MAX Ø
    # (machinist review round 5: a separate tap callout per hole put two
    # leaders on one small hole, arrowheads stacked): the tap line above, the
    # countersink symbol (DIMENSION_PREFIXES) before the Ø and the included
    # angle after its MAX (draw_pd_support_bar.COUNTERSINK_SUFFIX), the faces
    # and the mate the hole's banded row height and station serve below. The
    # thread class is the title block's (rule 2). The pivot is one hole
    # countersunk on both faces: no "2X", which on the hook taps' callout
    # counts holes (r6 machinist review, rule 12).
    # The hook taps' route (delegated ruling 2026-11-07, FoPdFab2 Q1):
    # spotted through the MHA-PD-14 base's holes at assembly, which sets
    # their stations (HOOK_TAP_REFERENCE_NAMES, printed REF). The pivot's
    # ±.002 is an owner exception (pd-support-bar.yaml RV-01).
    "PivotCskDia": "BOTH FACES\nLOCATES MHA-PD-VN-57",
    "BracketCskDia": "BOTH FACES\nSPOT THRU MHA-PD-14 AT ASSEMBLY",
    # The slot width's upper limit is the head's: wider, the MHA-SH-VN-53
    # head bears on less floor than over a round hole (CLAMP_HEAD_BEARING_MIN)
    # and nears the counterbore's wall (clamp_slot_head_clearance). The
    # counterbored slot names its mate once, on the width (rule 4, one feature
    # names its mate once; round 4 machinist review read "MAX SEATS ... HEADS"
    # as rationale): the standard form, a clearance for the screw. Short
    # lines: detail C is 2:1 in a corner. The slot width's broken leader runs
    # down its text's left end to the underline, so the widest row's first
    # glyph rode that line (machinist review round 4). A no-break space each
    # side of the widest row widens the block by a space past every glyph;
    # the centred rows stand clear.
    "ClampSlotWidth": "\u00a0THRU, CLEARANCE FOR\u00a0\nMHA-SH-VN-53",
    # The counterbore slot shares the through slot's radius centres, the one
    # .12 detail C dimensions (rule 12; round 4 machinist review). Two short
    # lines keep the block inside its old width, clear of section B-B.
    "ClampSlotCboreWidth": "ON .12\nSLOT CENTRES",
}
# Above the countersinks' Ø: the tap each callout carries (DIMENSION_CALLOUTS).
DIMENSION_CALLOUTS_ABOVE = {
    "PivotCskDia": f"TAP {PIVOT_TAP_THREAD} UNC THRU",
    "BracketCskDia": f"2X TAP {BRACKET_TAP_SPEC.size} UNC THRU",
}
# The slot widths' count: both west slots share one detail. The countersinks
# read in rule 26's form, the countersink symbol before the Ø; a diameter's
# prefix replaces its native Ø token, so the prefix restates it (round 6
# printed "90° CSK .169" with no Ø).
_COUNTERSINK_PREFIX = "<HOLE-SINK><MOD-DIAM>"
DIMENSION_PREFIXES = {
    ("ClampSlotProfile", "ClampSlotWidth"): "2X ",
    ("ClampSlotCboreProfile", "ClampSlotCboreWidth"): "2X ",
    ("CountersinkReference", "PivotCskDia"): _COUNTERSINK_PREFIX,
    ("CountersinkReference", "BracketCskDia"): _COUNTERSINK_PREFIX,
}
# Under the round counterbores' native callout: the mate in the standard
# clearance form, the screw and the taps it threads into (round 4 machinist
# review: "LOCATE TO" read as an instruction). The holes are drilled at the
# printed row and stations, whose title-block ±.005 closes the MHA-SH-02
# taps' fixed-fastener stack (build_pd_support_bar.CLAMP_POSITION_BAND).
CLAMP_CBORE_CALLOUT = "CLEARANCE FOR MHA-SH-VN-53\nINTO MHA-SH-02 TAPS"
# The round holes' drill, written after their size in the native THRU row
# (rule 26: size, then process, then depth; the counterbore is its symbol).
CLAMP_HOLE_PROCESS = "DRILL"

# The platen guide MHA-PD-11 hangs by its top rail's underside on the top
# face and slides along it (pd_platen_guide_spec's own "bar_slide" face is
# its mate); the platen MHA-PD-02's back slides across the front face: the
# slide grade, rule 6.  Each symbol carries its one reason on its own shelf,
# naming the part that slides there by its drawing number (rules 4 and 7:
# flagged where it applies), as MHA-PD-11's own slide symbol does.
# PlanarFace offsets run along the outward normal (point . normal).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "top_slide",
        MACHINED_UM,
        PlanarFace((0, 1, 0), BAR_HEIGHT / 2.0),
        production_method=f"SLIDES ON {_config.parts('pd-platen-guide')['number']}",
        display_unit=UNIT,
    ),
    SurfaceFinishControl(
        "front_slide",
        MACHINED_UM,
        PlanarFace((0, 0, -1), BAR_DEPTH / 2.0),
        production_method=f"SLIDES ON {_config.parts('pd-platen')['number']}",
        display_unit=UNIT,
    ),
)

# The back face's view is the unlabelled principal view; the front face's is
# a removed rear view, lettered, its viewing arrow on section A-A pointing at
# the front face (rules 9 and 26). Both are at the sheet's scale, so neither
# prints one.
FRONT_FACE_VIEW_LETTER = "D"
BACK_VIEW_CAPTION = f"VIEW {FRONT_FACE_VIEW_LETTER}"
# The two face views mirror each other, so the end every station runs from is
# named at that end in both views (rule 10: one end, plainly the same one).
STATION_END_LABEL = "END A"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
