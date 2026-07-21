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
PIVOT_BORE_DIA = 6.125  # final reamed bore limits 6.10-6.15

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HandleProfile": {"HandleLength", "CollarLength", "PeakStation"},
    "PivotBoreProfile": {"PivotBoreDia"},
}

DRAWING_NOTES = "\n".join(
    (
        "ALL AXIAL STATIONS ARE FROM THE FLAT COLLAR FACE; 90.00 IS WOOD OVERALL.",
        "THEORETICALLY EXACT TURNING PROFILE: COLLAR <MOD-DIAM>11.00 X 6.00,",
        "  NECK <MOD-DIAM>9.60, MAX <MOD-DIAM>22.00 AT 62.00, BUTT FLAT <MOD-DIAM>7.00.",
        "R256.00 BASIC ARC RUNS FROM COLLAR NECK AT 6.00 TO MAX AT 62.00;",
        "  R56.02 BASIC ARC RUNS FROM MAX TO BUTT FLAT AT 90.00.",
        "ARCS ARE TANGENT AT MAX ONLY. JUNCTIONS AT 6.00 AND 90.00 MUST REMAIN",
        "  AS-TURNED SHARP CORNERS; NO BLEND, RADIUS, OR CHAMFER.",
        "TURN COLLAR PROFILE INTEGRAL WITH HANDLE BLANK.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
