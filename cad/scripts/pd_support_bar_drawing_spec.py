"""Pure-data drawing contract for the support bar (MHA-PD-007).

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
from pd_support_bar_spec import (
    BAR_BAND_PLACES,
    BAR_DEPTH,
    BAR_HEIGHT,
    BRACKET_TAP_SPEC,
    PIVOT_TAP_THREAD,
    TAP_CSK_ANGLE_DEG,
)

# SOLIDWORKS swTolType_e single limits: the nominal prints followed by MIN or
# MAX, so the model value is the limit itself.
TOL_MIN = 5  # swTolMIN
TOL_MAX = 6  # swTolMAX
HOLE_POSITION_PLACES = 3  # the hanger holes' ±0.065 prints .XXX
# The clamp holes' row height and stations print .XX: their position band
# (build_pd_support_bar.CLAMP_POSITION_BAND) is the MHA-SH-002 back-arc taps'
# fixed-fastener stack, so the title block's .X ±0.8 would miss the taps.
CLAMP_POSITION_PLACES = 2
# The clamp counterbores' depth prints .XX: under its band the shallowest
# depth still sinks the clamp-screw head below the front face the platen
# slides across (build_pd_support_bar.CLAMP_HEAD_RECESS).
CLAMP_CBORE_DEPTH_PLACES = 2
# The round counterbores' native callout prints its Ø at the document's two
# places, under the title block's DRILLED HOLES row.
CLAMP_HOLE_CALLOUT_PLACES = 2
# The west clamp slots (build_pd_support_bar, owner ruling 2026-10-15 option
# A): the width is the round hole's, carrying its drilled +0.10/-0 at .XX;
# the travel and the counterbore's width and travel print .XXX, the places
# whose title-block band still closes the slots' worst-case column span and
# keeps the screw head inside the counterbore
# (build_pd_support_bar.clamp_slot_closure_margin, clamp_slot_head_clearance).
CLAMP_SLOT_WIDTH_PLACES = 2
CLAMP_SLOT_PLACES = 3
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
    "ClampSlotCboreProfile": {"ClampSlotCboreWidth", "ClampSlotCboreTravel"},
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
    "PivotTapProfile": {"PivotTapDrillDia": 2},
    "CountersinkReference": {"PivotCskDia": 1, "BracketCskDia": 1},
    "ClampSlotProfile": {
        "ClampSlotWidth": CLAMP_SLOT_WIDTH_PLACES,
        "ClampSlotTravel": CLAMP_SLOT_PLACES,
    },
    "ClampSlotCboreProfile": dict.fromkeys(
        ("ClampSlotCboreWidth", "ClampSlotCboreTravel"), CLAMP_SLOT_PLACES
    ),
    "ClampSlotCounterbores": {"ClampSlotCboreDepth": CLAMP_CBORE_DEPTH_PLACES},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    **SHEET_PRECISION,
    "BarProfile": {**SHEET_PRECISION["BarProfile"], "Height": BAR_BAND_PLACES},
    "Bar": {"Depth": BAR_BAND_PLACES},
}

# Below each value: what the band or limit is for, naming the mating part.
_CSK = f"{TAP_CSK_ANGLE_DEG:.0f}\u00b0 CSK"
_HOOK_TAPS = "MHA-PD-014 HOOK TAPS"
DIMENSION_CALLOUTS = {
    "Height": "MHA-PD-011\nHANGS ON IT",
    "Depth": "MHA-VN-041 TIP RECESS AND\nMHA-VN-043 SCREW TIPS",
    # The two rows print on one line at 1:2 though they are separate rows
    # (the hanger row from the machine layout, the clamp row at mid-height).
    "HangerRowHeight": f"MHA-VN-041 PIVOT AND\n{_HOOK_TAPS},\nNOT ON THE CLAMP ROW",
    "ClampRowHeight": "BAR\nMID-HEIGHT",
    "PivotTapStation": "MHA-VN-041 PIVOT",
    "BracketTapStation1": _HOOK_TAPS,
    "BracketTapStation2": _HOOK_TAPS,
    # The thread class is the title block's (rule 2).
    "PivotTapDrillDia": f"TAP {PIVOT_TAP_THREAD} UNC THRU",
    # At most 24 characters a line: the latch-hook taps' callout leader
    # passes just right of this text (layout audit: leader-through-text).
    "PivotCskDia": f"2X {_CSK} BOTH FACES,\nMHA-VN-041 BEARS OUTSIDE",
    "BracketCskDia": f"2X {_CSK}\nBOTH FACES, {BRACKET_TAP_SPEC.size} TAPS",
    # The west slots: why they are slots, and the screws whose heads their
    # counterbores sink, as the round counterbores' callout says.
    "ClampSlotWidth": "THRU\nSLOTS TAKE UP\nCOLUMN PITCH",
    "ClampSlotCboreWidth": "C'BORE",
    "ClampSlotCboreDepth": "MHA-VN-021 HEADS\nBELOW SLIDE FACE",
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
CLAMP_TAP_MATE = "LOCATE TO MHA-SH-002 TAPS"
CLAMP_CBORE_CALLOUT = f"{CLAMP_TAP_MATE}\nMHA-VN-021 HEADS BELOW SLIDE FACE"

# The platen hangs by its top rail's underside on the top face and slides
# across the front face (build_pd_support_bar; pd_platen_guide_spec's own
# "bar_slide" face is the mate of the top one): the slide grade, rule 6.
# PlanarFace offsets run along the outward normal (point . normal).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "top_slide", MACHINED_UM, PlanarFace((0, 1, 0), BAR_HEIGHT / 2.0)
    ),
    SurfaceFinishControl(
        "front_slide", MACHINED_UM, PlanarFace((0, 0, -1), BAR_DEPTH / 2.0)
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
