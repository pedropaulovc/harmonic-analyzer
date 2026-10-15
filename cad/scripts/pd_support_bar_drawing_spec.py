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
  in the front-face view) and its height from the top face.
* The platen hangs on the top face and slides across the front face: both
  carry the slide roughness (``SURFACE_FINISHES``, drawing-guidelines rule 6).

The rows' nominals are the build's (``build_pd_support_bar``), which owns the
bar length and the clamp-screw stations.
"""

from __future__ import annotations

from _gtol_planar import PlanarFace
from _hole_spec import THREAD_MAJOR_MM
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pd_support_bar_spec import (
    BAR_BAND_PLACES,
    BAR_DEPTH,
    BAR_HEIGHT,
    BRACKET_TAP_SPEC,
    PIVOT_TAP_FULL_THREAD_MIN,
    PIVOT_TAP_THREAD,
    TAP_CSK_ANGLE_DEG,
)

# SOLIDWORKS swTolType_e single limits: the nominal prints followed by MIN or
# MAX, so the model value is the limit itself.
TOL_MIN = 5  # swTolMIN
TOL_MAX = 6  # swTolMAX
HOLE_POSITION_PLACES = 3  # the hanger holes' ±0.065 prints .XXX
# The clamp counterbores' depth prints .XX: under its band the shallowest
# depth still sinks the clamp-screw head below the front face the platen
# slides across (build_pd_support_bar.CLAMP_HEAD_RECESS).
CLAMP_CBORE_DEPTH_PLACES = 2
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
    "PivotTap": {"DrillDepth"},
    "PivotThreadReference": {"ThreadMin"},
    "CountersinkReference": {"PivotCskDia", "BracketCskDia"},
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
        "ClampRowHeight": 1,
        **dict.fromkeys(CLAMP_STATION_NAMES, 1),
    },
    "PivotTapProfile": {"PivotTapDrillDia": 2},
    "PivotTap": {"DrillDepth": 1},
    "PivotThreadReference": {"ThreadMin": 1},
    "CountersinkReference": {"PivotCskDia": 1, "BracketCskDia": 1},
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
    "Depth": "PIVOT TAP FLOOR AND\nMHA-VN-043 SCREW TIPS",
    # The two rows print on one line at 1:2 though they are separate rows
    # (the hanger row from the machine layout, the clamp row at mid-height).
    "HangerRowHeight": f"MHA-VN-041 PIVOT AND\n{_HOOK_TAPS},\nNOT ON THE CLAMP ROW",
    "ClampRowHeight": "BAR\nMID-HEIGHT",
    "PivotTapStation": "MHA-VN-041 PIVOT",
    "BracketTapStation1": _HOOK_TAPS,
    "BracketTapStation2": _HOOK_TAPS,
    # The thread class is the title block's (rule 2).
    "PivotTapDrillDia": f"TAP {PIVOT_TAP_THREAD} UNC",
    "DrillDepth": "FLAT BOTTOM",
    # Rule 20: the blind full thread falls short of rule 18's 1.5D; the
    # sheet states the shortfall as a plain fact (the 9.0 bar's floor).
    "ThreadMin": f"FULL THREAD ({PIVOT_TAP_FULL_THREAD_MIN / THREAD_MAJOR_MM[PIVOT_TAP_THREAD]:.2f}D)",
    "PivotCskDia": f"{_CSK}, MHA-VN-041\nSHOULDER BEARS OUTSIDE",
    "BracketCskDia": f"2X {_CSK}\nBOTH FACES, {BRACKET_TAP_SPEC.size} TAPS",
}
# Under the counterbores' native callout: the screws whose heads they sink,
# and why the depth has a floor (the heads' worst case stays sub-flush).
CLAMP_CBORE_CALLOUT = "MHA-VN-021 HEADS BELOW SLIDE FACE"

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
