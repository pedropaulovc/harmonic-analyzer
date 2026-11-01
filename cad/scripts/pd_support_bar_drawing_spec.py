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
* The platen hangs on the top face and slides across the front face: both
  carry the slide roughness (``SURFACE_FINISHES``, drawing-guidelines rule 6).

The rows' nominals are the build's (``build_pd_support_bar``), which owns the
bar length and the clamp-screw stations.
"""

from __future__ import annotations

from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from _column_clamp_interface import BAR_DEPTH
from pd_support_bar_spec import (
    BAR_BAND_PLACES,
    BAR_HEIGHT,
    BRACKET_TAP_SPEC,
    HOLE_POSITION_PLACES,
    PIVOT_TAP_THREAD,
    TAP_CSK_ANGLE_DEG,
    UNIT,
)

# SOLIDWORKS swTolType_e single limits: the nominal prints followed by MIN or
# MAX, so the model value is the limit itself.
TOL_MIN = 5  # swTolMIN
TOL_MAX = 6  # swTolMAX
# The clamp holes' row height and stations print .XXX: their position band
# (build_pd_support_bar.CLAMP_POSITION_BAND) is the MHA-SH-02 back-arc taps'
# fixed-fastener stack, which the title block's .XX ±.01 would overrun.
CLAMP_POSITION_PLACES = 3
# The clamp counterbores' depth prints .XX: under its band the shallowest
# depth still sinks the clamp-screw head below the front face the platen
# slides across (build_pd_support_bar.CLAMP_HEAD_RECESS).
CLAMP_CBORE_DEPTH_PLACES = 2
# Every native Hole Wizard length (the round counterbores' Ø, depth) prints
# .XXX, under the title block's DRILLED HOLES row.
CLAMP_HOLE_CALLOUT_PLACES = 3
# By native Hole Wizard variable: the round counterbores' Ø's and depth, the
# latch-hook taps' drill.
CLAMP_CALLOUT_PRECISION = {
    "hw-thruholedia": CLAMP_HOLE_CALLOUT_PLACES,
    "hw-cbdia": CLAMP_HOLE_CALLOUT_PLACES,
    "hw-cbdepth": CLAMP_CBORE_DEPTH_PLACES,
}
BRACKET_TAP_CALLOUT_PRECISION = {"hw-thrutapdrldia": 3}
# The west slots' runs need .XXX to close the column-pitch stack, and their
# width carries the drilled holes' +.004/0 at .XXX. Their counterbore width
# carries explicit asymmetric limits: the minimum (.330) clears the head's
# full-float envelope, while the upper deviation stays the ordinary .XX
# band. The round counterbores' head stays coaxial, while a slid head adds
# the slot run's .XXX overrun (build_pd_support_bar.clamp_slot_head_clearance),
# so the callout says the minimum is for the slid head (3de09b9 machinist
# review).
CLAMP_SLOT_WIDTH_PLACES = 3
CLAMP_SLOT_PLACES = 3
CLAMP_SLOT_CBORE_WIDTH_PLACES = 3
CLAMP_SLOT_CBORE_WIDTH_LIMITS = (-0.127, 0.254)  # -.005/+.010
HANGER_STATION_NAMES = ("PivotTapStation", "BracketTapStation1", "BracketTapStation2")
CLAMP_STATION_NAMES = (
    "ClampStation1",
    "ClampStation2",
    "ClampStation3",
    "ClampStation4",
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"Length", "Height"},
    "Bar": {"Depth"},
    "HangerRowReference": {"HangerRowHeight", *HANGER_STATION_NAMES},
    "ClampRowReference": {"ClampRowHeight", *CLAMP_STATION_NAMES},
    "PivotTapProfile": {"PivotTapDrillDia"},
    "CountersinkReference": {"PivotCskDia", "BracketCskDia"},
    "ClampSlotProfile": {"ClampSlotWidth", "ClampSlotTravel"},
    # The counterbore's run is the slot's: one .118 between the shared end
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
        **dict.fromkeys(CLAMP_STATION_NAMES, CLAMP_POSITION_PLACES),
    },
    "PivotTapProfile": {"PivotTapDrillDia": 3},
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

# Below each value: what the band or limit is for, naming the mating part.
_CSK = f"{TAP_CSK_ANGLE_DEG:.0f}\u00b0 CSK"
_HOOK_TAPS = "MHA-PD-14 HOOK TAPS"
DIMENSION_CALLOUTS = {
    "Height": "MHA-PD-11\nHANGS ON IT",
    "Depth": "MHA-PD-VN-57 TIP RECESS AND\nMHA-SH-VN-52 SCREW TIPS",
    # The two rows print on one line at 1:2 though they are separate rows
    # (the hanger row from the machine layout, the clamp row on the SH column
    # clamps' line, both from the top face the platen hangs on).
    "HangerRowHeight": f"MHA-PD-VN-57 PIVOT AND\n{_HOOK_TAPS},\nNOT ON THE CLAMP ROW",
    # The clamp row's band is the MHA-SH-02 taps' (CLAMP_POSITION_BAND), so
    # its mate stands at the dimension, not only under the hole callout.
    "ClampRowHeight": "MHA-SH-02\nTAPS",
    "PivotTapStation": "MHA-PD-VN-57 PIVOT",
    "BracketTapStation1": _HOOK_TAPS,
    "BracketTapStation2": _HOOK_TAPS,
    # The thread class is the title block's (rule 2).
    "PivotTapDrillDia": f"TAP {PIVOT_TAP_THREAD} UNC THRU",
    # The historical 24-character lane predates the full vendor number;
    # draw_pd_support_bar now moves both hook callouts right of this text.
    # One hole countersunk on both faces: no "2X", which on the hook taps'
    # callout counts holes (r6 machinist review, rule 12).
    "PivotCskDia": f"{_CSK} BOTH FACES,\nMHA-PD-VN-57 BEARS OUTSIDE",
    "BracketCskDia": f"2X {_CSK}\nBOTH FACES, {BRACKET_TAP_SPEC.size} TAPS",
    # The west slots (rule 4: each band names its mate): the slots' run and
    # stations take up the pitch of the MHA-SH-02 clamp taps the screws land
    # in (build_pd_support_bar.clamp_slot_closure_margin), and the whole
    # travel is spent on that pitch, so their limits and stations keep the
    # full take-up (the r6 machinist read "take up" as licence to loosen
    # them, the 2026-10-23 review as travel needing only to be "enough").
    # The slot width's upper limit is the head's: wider, the MHA-SH-VN-53
    # head bears on less floor than over a round hole (CLAMP_HEAD_BEARING_MIN)
    # and nears the counterbore's wall (clamp_slot_head_clearance); the
    # 2026-10-23 review read the take-up reason alone as no reason for the
    # width's band. The counterbore's minimum clears the slid MHA-SH-VN-53
    # head; the reason names no limit word, which under the two-sided band
    # read as ".335 MIN" (machinist review round 2). Short lines: detail C is
    # 2:1 in a corner, and two lines of at most 15 characters keep the block
    # between section B-B and the 440.50 line (farm run after round 2: an
    # 18-character "MHA-SH-VN-53 HEADS" row crowded section B-B).
    "ClampSlotWidth": (
        "THRU, MAX SEATS\nMHA-SH-VN-53 HEADS;\nTRAVEL AND STATIONS\n"
        "KEEP THE FULL TAKE-UP\nOF MHA-SH-02 PITCH"
    ),
    "ClampSlotCboreWidth": "CLEARS SLIDING\nMHA-SH-VN-53",
    "ClampSlotCboreDepth": "MHA-SH-VN-53\nHEADS BELOW\nSLIDE FACE",
}
# The slot widths' count: both west slots share one detail.
DIMENSION_PREFIXES = {
    ("ClampSlotProfile", "ClampSlotWidth"): "2X ",
    ("ClampSlotCboreProfile", "ClampSlotCboreWidth"): "2X ",
}
# Under the round counterbores' native callout: the taps the holes' banded
# row height and stations locate to (rule 4: the tight band names its mate, as
# the latch hook's SCREW_HOLE_MATE does), then the screws whose heads they
# sink, and why the depth has a floor (the heads' worst case stays sub-flush).
CLAMP_TAP_MATE = "LOCATE TO MHA-SH-02 TAPS"
CLAMP_CBORE_CALLOUT = f"{CLAMP_TAP_MATE}\nMHA-SH-VN-53 HEADS BELOW SLIDE FACE"

# The platen hangs by its top rail's underside on the top face and slides
# across the front face (build_pd_support_bar; pd_platen_guide_spec's own
# "bar_slide" face is the mate of the top one): the slide grade, rule 6.
# PlanarFace offsets run along the outward normal (point . normal).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "top_slide",
        MACHINED_UM,
        PlanarFace((0, 1, 0), BAR_HEIGHT / 2.0),
        display_unit=UNIT,
    ),
    SurfaceFinishControl(
        "front_slide",
        MACHINED_UM,
        PlanarFace((0, 0, -1), BAR_DEPTH / 2.0),
        display_unit=UNIT,
    ),
)

FACE_VIEW_CAPTION = "VIEW ON BACK FACE"
BACK_VIEW_CAPTION = "VIEW ON FRONT FACE"
# The face views mirror each other, so the end every station runs from is
# named at that end in both views (rule 10: one end, plainly the same one).
STATION_END_LABEL = "END A"
# Each slide grade's reason, beside its symbol (rule 7: flagged where it
# applies), so the sheet carries no general note.
TOP_FINISH_REASON = "PLATEN HANGS HERE"
FRONT_FINISH_REASON = "PLATEN SLIDES HERE"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
