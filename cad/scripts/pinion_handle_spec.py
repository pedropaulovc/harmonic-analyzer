r"""Pure-data dimensional contract shared by the pinion turning handle and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A turned tee: a fat grip cylinder with a
domed cap, a cross rod through the grip, and a blind tubular hub that seats over
the pinion arbor stub.  The nominals drive the part's named equation globals AND
the drawing's coordinate math; the marked-dimension map keeps the part marks and
drawing keeps in lockstep (``test_pinion_handle_drawing.py``).
"""

from __future__ import annotations

from _fit_limits import REAM_SLIDE
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_handle_geometry import (
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    GRIP_DIA as GRIP_DIA,
    GRIP_LEN as GRIP_LEN,
    ROD_DIA as ROD_DIA,
    ROD_DOWN as ROD_DOWN,
    ROD_HOLE_DIA as ROD_HOLE_DIA,
    ROD_SPAN as ROD_SPAN,
    ROD_UP as ROD_UP,
    TUBE_ID as TUBE_ID,
    TUBE_LEN as TUBE_LEN,
    TUBE_OD as TUBE_OD,
    WALL_T as WALL_T,
)

# Press/ream bands peculiar to this part (per _fit_limits.py's contract, a
# part-specific band lives beside the nominal it tolerances, not in the shared
# fit-class table).  Symmetric about each nominal; rendered through
# :func:`fit_limits` so a nominal retune can never leave the released MAX/MIN
# text stale (codex #359).
ROD_PRESS_BAND = (0.0025, -0.0025)  # turned cross-rod OD tolerance
ROD_HOLE_REAM_BAND = (0.005, -0.005)  # body cross-hole ream tolerance
TUBE_ID_BAND = REAM_SLIDE
GRIP_LENGTH_TOLERANCE_MM = 0.10
TUBE_LENGTH_BAND = (0.10, 0.00)
ROD_SPAN_TOLERANCE_MM = 0.10

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GripProfile": {"GripDia"},
    "Grip": {"GripLen"},
    "TubeProfile": {"TubeOd", "TubeId"},
    "Tube": {"TubeLen"},
    "RodProfile": {"RodDia"},
    "Rod": {"RodSpan"},
    "RodHoleProfile": {"RodHoleDia"},
}

SURFACE_FINISHES = (
    SurfaceFinishControl(
        key="final_bore",
        roughness_um=MACHINED_UM,
        face=CylinderFace(diameter_mm=TUBE_ID),
    ),
)

DRAWING_NOTES = "\n".join(
    (
        "DATUM A IS FINAL REAMED BORE AXIS; DATUM B IS FLAT HUB END.",
        "TURN GRIP, WALL AND HUB IN ONE SETUP. OPPOSITE GRIP FACE:",
        f"  SPHERICAL CROWN SR{CAP_RADIUS:.2f}+/-0.10; {CAP_SAG:.2f} REF HIGH.",
        "CROWN ROOT CIRCLE IS AN INTENTIONAL PROFILE BREAK; DO NOT BLEND.",
        "BODY CROSS-HOLE AXIS POSITION IS CONTROLLED BY THE",
        "  BOXED BASIC DIMENSION AND ATTACHED <MOD-DIAM>0.05 | A | B FRAME.",
        f"PRESSED ROD AXIAL PLACEMENT: DATUM A TO LOWER END {ROD_DOWN:.2f}+/-0.10.",
        f"HUB PROJECTION: DATUM B TO GRIP FACE {TUBE_LEN + WALL_T:.2f} +0.10/-0.00.",
        "FINAL PART CONSISTS OF TURNED BODY AND PRESSED CROSS ROD.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
