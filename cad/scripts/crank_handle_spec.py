r"""Pure-data dimensional contract shared by the crank handle and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A turned stained-oak pear grip on the
crank-arm pivot: an integral collar profile at the crank end, a waisted neck, a smooth
twin-arc swell to the Ø21 max, and a blunt domed butt with a flat cap.  The
pear silhouette is two internally-tangent arcs, so the swell/neck/butt
DIAMETERS derive from the profile geometry and cannot be marked without
over-defining; the drawing therefore dimensions the clean AXIAL stations
(overall length, collar length, peak station) and gives the diameters as a
turning schedule note.  The nominals drive the part's named equation globals
AND the drawing's coordinate math; the marked-dimension map keeps the part
marks and drawing keeps in lockstep (``test_crank_handle_drawing.py``).
"""

from __future__ import annotations

from _fit_limits import band_text

# 2026-09-02 user re-read of the pass-2 model against ch11 p.14 and the ch30
# p002 front view: the 44 mm egg of the 2026-09 photo re-derive (ch11
# page002_img03 at 12.6 px/mm) read too STUBBY -- the grip is longer and
# slimmer than that egg: overall 58 from the collar face, swell 21 across at
# 0.62 of the length, neck Ø11, butt cap Ø10; the brass collar stays 15 x 7.
HANDLE_LENGTH = 58.0  # overall length (collar face to butt cap)
HANDLE_MAX_DIA = 21.0  # max diameter at the swell
COLLAR_LENGTH = 7.0  # brass collar length
COLLAR_DIA = 15.0  # brass collar OD
NECK_R = 5.5  # waist just below the collar (neck Ø11)
PEAK_X = 36.0  # axial station of the maximum diameter
CAP_R = 5.0  # flat butt cap radius (Ø10)
PIVOT_BORE_DIA = 6.125  # final reamed bore limits 6.10-6.15
# Symmetric ream band about the mid nominal: 6.15 MAX / 6.10 MIN.
PIVOT_BORE_BAND = (0.025, -0.025)
# Wood overall, (upper, lower) mm.  Unilateral: the butt is trimmed to length,
# so it may come short of the basic profile but never long.  Applied to the
# MODEL dimension by build_crank_handle, and rendered into DRAWING_NOTES below
# -- both from THIS constant, so a retune cannot leave the note disagreeing
# with the print.
HANDLE_LENGTH_BAND = (0.000, -0.250)
# Collar OD, the datum-A feature.  Symmetric, general turned class.
COLLAR_DIA_TOL_MM = 0.10


_FRONT_DX = PEAK_X - COLLAR_LENGTH
_FRONT_DH = HANDLE_MAX_DIA / 2.0 - NECK_R
FRONT_PROFILE_R = (_FRONT_DX**2 + _FRONT_DH**2) / (2.0 * _FRONT_DH)
_REAR_DX = HANDLE_LENGTH - PEAK_X
_REAR_DH = HANDLE_MAX_DIA / 2.0 - CAP_R
REAR_PROFILE_R = (_REAR_DX**2 + _REAR_DH**2) / (2.0 * _REAR_DH)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HandleProfile": {"HandleLength", "CollarLength", "PeakStation"},
    "PivotBoreProfile": {"PivotBoreDia"},
}

DRAWING_NOTES = "\n".join(
    (
        f"DATUM A IS THE <MOD-DIAM>{COLLAR_DIA:.2f}+/-{COLLAR_DIA_TOL_MM:.2f} COLLAR OD DERIVED AXIS; THE A SYMBOL",
        "  ATTACHES TO THAT OD. DATUM B IS THE FLAT COLLAR END FACE.",
        "TURN COLLAR INTEGRAL. FINAL BORE LIMITS APPLY FULL LENGTH.",
        f"ALL AXIAL STATIONS ARE FROM B; {HANDLE_LENGTH:.2f}{band_text(HANDLE_LENGTH_BAND)} IS WOOD OVERALL.",
        f"BASIC TRUE GRIP PROFILE (ALL VALUES BASIC): <MOD-DIAM>{2.0 * NECK_R:.2f} AT X{COLLAR_LENGTH:.2f};",
        f"  <MOD-DIAM>{HANDLE_MAX_DIA:.2f} AT X{PEAK_X:.2f}; <MOD-DIAM>{2.0 * CAP_R:.2f} AT X{HANDLE_LENGTH:.2f}. TWO CIRCULAR ARCS",
        f"  TANGENT AT X{PEAK_X:.2f}: R{FRONT_PROFILE_R:.6f} FROM X{COLLAR_LENGTH:.2f} TO X{PEAK_X:.2f};",
        f"  R{REAR_PROFILE_R:.6f} FROM X{PEAK_X:.2f} TO X{HANDLE_LENGTH:.2f}.",
        "PROFILE 0.50 | A | B APPLIES TO SHOULDER FACE AND BOTH ARCS FROM BASIC",
        f"  X{COLLAR_LENGTH:.2f} TO ACTUAL BUTT TRIM FACE; THEORETICAL PROFILE EXTENDS TO X{HANDLE_LENGTH:.2f}.",
        f"ACTUAL BUTT FACE AT {HANDLE_LENGTH:.2f}{band_text(HANDLE_LENGTH_BAND)} TRIMS THE BASIC PROFILE; ITS EDGE AND",
        f"  THE BASIC-{COLLAR_LENGTH:.2f} JUNCTION ARE SHARP. NO BLEND, RADIUS, OR CHAMFER.",
        "USE CLEAR STRAIGHT GRAIN PARALLEL TO TURNING AXIS.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "flat collar end perpendicularity": "0.10",
    "full-length bore total runout": "0.10",
    "turned handle profile": "0.50",
}
