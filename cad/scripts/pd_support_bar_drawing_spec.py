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
* The clamp row's stations run from the bar's end on the sheet's left in the
  front-face view (x = +226) and its height from the top face.

The rows' nominals are the build's (``build_pd_support_bar``), which owns the
bar length and the clamp-screw stations.
"""

from __future__ import annotations

from pd_support_bar_spec import (
    BAR_BAND_PLACES,
    BRACKET_TAP_SPEC,
    PIVOT_TAP_THREAD,
    TAP_CSK_ANGLE_DEG,
)

# SOLIDWORKS swTolType_e single limits: the nominal prints followed by MIN or
# MAX, so the model value is the limit itself.
TOL_MIN = 5  # swTolMIN
TOL_MAX = 6  # swTolMAX
HOLE_POSITION_PLACES = 3  # the hanger holes' ±0.065 prints .XXX
# The clamp counterbores' depth prints .XXX: under its band the shallowest
# depth still sinks the clamp-screw head below the front face the platen
# slides across (build_pd_support_bar.CLAMP_HEAD_RECESS).
CLAMP_CBORE_DEPTH_PLACES = 3
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
DIMENSION_CALLOUTS = {
    "Height": "RUNS BETWEEN MHA-PD-011\nRAILS UNDER MHA-PD-012",
    "Depth": "PIVOT TAP FLOOR AND\nMHA-VN-043 SCREW TIPS",
    "HangerRowHeight": "MHA-VN-041 PIVOT AND\nMHA-PD-014 HOOK TAPS",
    "PivotTapDrillDia": f"TAP {PIVOT_TAP_THREAD} UNC-2B",
    "DrillDepth": "FLAT BOTTOM",
    "ThreadMin": "FULL THREAD",
    "PivotCskDia": f"{_CSK}, MHA-VN-041\nSHOULDER BEARS OUTSIDE",
    "BracketCskDia": f"2X {_CSK}\nBOTH FACES, {BRACKET_TAP_SPEC.size} TAPS",
}

DRAWING_NOTES = "\n".join(
    (
        "UPPER VIEW: BACK FACE, CARRYING THE TRANSGEAR PIVOT AND LATCH-HOOK TAPS.",
        "LOWER VIEW: FRONT FACE. THE PLATEN SLIDES ON IT, SO THE CLAMP SCREW",
        "HEADS MUST SIT BELOW IT.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:6"
