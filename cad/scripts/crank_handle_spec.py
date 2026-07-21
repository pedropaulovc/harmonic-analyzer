r"""Pure-data dimensional contract shared by the crank handle and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A turned stained-oak pear grip on the
crank-arm pivot: an integral collar profile at the crank end, a waisted neck, a smooth
twin-arc swell to the Ø22 max, and a blunt domed butt with a flat cap.  The
pear silhouette is two internally-tangent arcs, so the swell/neck/butt
DIAMETERS derive from the profile geometry and cannot be marked without
over-defining; the drawing therefore dimensions the clean AXIAL stations
(overall length, collar length, peak station) and gives the diameters as a
turning schedule note.  The nominals drive the part's named equation globals
AND the drawing's coordinate math; the marked-dimension map keeps the part
marks and drawing keeps in lockstep (``test_crank_handle_drawing.py``).
"""

from __future__ import annotations

HANDLE_LENGTH = 90.0  # overall length (collar face to butt cap)
HANDLE_MAX_DIA = 22.0  # max diameter at the swell
COLLAR_LENGTH = 6.0  # brass collar length
COLLAR_DIA = 11.0  # brass collar OD
NECK_R = 4.8  # waist just below the collar (neck Ø9.6)
PEAK_X = 62.0  # axial station of the maximum diameter
CAP_R = 3.5  # flat butt cap radius (Ø7)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HandleProfile": {"HandleLength", "CollarLength", "PeakStation"},
}

DRAWING_NOTES = "\n".join(
    (
        "ALL AXIAL STATIONS ARE FROM THE FLAT COLLAR FACE; 90.00 IS WOOD OVERALL.",
        "TURNING SCHEDULE: COLLAR <MOD-DIAM>11.00 X 6.00, NECK <MOD-DIAM>9.60,",
        "  MAX <MOD-DIAM>22.00 AT 62.00, BUTT FLAT <MOD-DIAM>7.00.",
        "PROFILE ARCS R256.00 AND R56.02, TANGENT AT THE 62.00 MAX STATION;",
        "  BLEND TO COLLAR AND BUTT AS A SMOOTH PEAR CURVE, PROFILE TOLERANCE 0.50.",
        "TURN THE COLLAR PROFILE INTEGRAL WITH THE OAK HANDLE.",
        "BORE 6.10-6.15 THRU ON TURNING AXIS, Ra 3.2; WAX BORE AFTER FINISH.",
        "MATING PIN: <MOD-DIAM>5.95-5.98 X 98.5 UNDER HEAD; M4 X 0.7-6H X 8 DEEP",
        "  IN FREE END. RETAIN WITH <MOD-DIAM>12 WASHER AND M4 SCREW; END PLAY 0.3-0.8.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
