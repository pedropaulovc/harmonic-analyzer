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
    "HandleProfile": {"HandleLength", "CollarLength", "FrontArcCx"},
}

DRAWING_NOTES = "\n".join(
    (
        "AXIAL STATIONS ARE FROM THE COLLAR FACE.",
        "TURNING SCHEDULE (DIAMETERS): COLLAR <MOD-DIAM>11, NECK <MOD-DIAM>9.6, "
        "MAX <MOD-DIAM>22 AT STATION 62, BUTT CAP <MOD-DIAM>7.",
        "BLEND NECK-TO-MAX AND MAX-TO-BUTT AS ONE SMOOTH PEAR CURVE.",
        "TURN THE COLLAR PROFILE INTEGRAL WITH THE OAK HANDLE.",
        "RELEASE HOLD - DO NOT MANUFACTURE: DEFINE THE HANDLE PIVOT BORE/PIN,",
        "  RUNNING CLEARANCE, AND AXIAL RETENTION AT THE CRANK ARM.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
