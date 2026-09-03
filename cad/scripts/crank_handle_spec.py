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
# so it may come short of the profile but never long.  Applied to the MODEL
# dimension by build_crank_handle (drawing-simplicity-policy.md rule 2).
HANDLE_LENGTH_BAND = (0.000, -0.250)
# Collar OD.  Symmetric, general turned class.
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

# Notes: the turning schedule -- the diameters the pear arcs derive, which
# the axial-station dimensions on the view cannot carry -- and the grain
# (drawing-simplicity-policy.md rule 6).  No tolerance, no datum letters.
DRAWING_NOTES = "\n".join(
    (
        f"TURN COLLAR INTEGRAL, <MOD-DIAM>{COLLAR_DIA:.2f}; STATIONS X ARE FROM THE COLLAR FACE.",
        f"GRIP: <MOD-DIAM>{2.0 * NECK_R:.2f} NECK AT X{COLLAR_LENGTH:.2f}; <MOD-DIAM>{HANDLE_MAX_DIA:.2f} SWELL AT X{PEAK_X:.2f}; <MOD-DIAM>{2.0 * CAP_R:.2f} CAP AT X{HANDLE_LENGTH:.2f}.",
        f"ARCS TANGENT AT X{PEAK_X:.2f}: R{FRONT_PROFILE_R:.2f} COLLAR TO SWELL, R{REAR_PROFILE_R:.2f} SWELL TO CAP.",
        "CLEAR STRAIGHT GRAIN ALONG THE TURNING AXIS.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
