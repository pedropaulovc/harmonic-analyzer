r"""Pure-data dimensional contract shared by the pinion turning handle and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A turned tee: a fat grip cylinder with a
domed cap, a cross rod through the grip, and a blind tubular hub that seats over
the pinion arbor stub.  The nominals drive the part's named equation globals AND
the drawing's coordinate math; the marked-dimension map keeps the part marks and
drawing keeps in lockstep (``test_pinion_handle_drawing.py``).
"""

from __future__ import annotations

GRIP_DIA = 23.0  # grip cylinder OD
GRIP_LEN = 14.0  # grip length along the arbor (z -7..+7)
CAP_SAG = 2.0  # domed south cap crown height
ROD_DIA = 6.0  # cross rod
ROD_DOWN = 42.0  # cross-rod arm, one side
ROD_UP = 43.0  # cross-rod arm, other side
TUBE_OD = 10.5  # blind hub cap OD over the arbor stub
TUBE_ID = 8.0  # = the arbor stub Ø8
TUBE_LEN = 10.0  # stub seat depth
WALL_T = 2.0  # blind wall between grip and tube
CAP_RADIUS = ((GRIP_DIA / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)

ROD_SPAN = ROD_DOWN + ROD_UP  # 85.0: cross-rod tip to tip

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GripProfile": {"GripDia"},
    "Grip": {"GripLen"},
    "TubeProfile": {"TubeOd", "TubeId"},
    "Tube": {"TubeLen"},
    "RodProfile": {"RodDia"},
    "Rod": {"RodSpan"},
}

DRAWING_NOTES = "\n".join(
    (
        "TURN THE GRIP, WALL AND HUB IN ONE SETUP ON THE ARBOR AXIS.",
        "GRIP: <MOD-DIAM>23 X 14.00 LONG. HUB: <MOD-DIAM>10.5 OD; BORE 8.010-8.025",
        "  X 10.00 DEEP FROM THE FLAT END, BLIND; 2.00 END WALL; BORE Ra 1.6.",
        f"DOME THE OPPOSITE GRIP FACE TO SPHERICAL R{CAP_RADIUS:.2f}, 2.00 AXIAL CROWN.",
        "CROSS ROD <MOD-DIAM>6; 42.00 AND 43.00 FROM THE GRIP AXIS.",
        "RELEASE HOLD - DO NOT MANUFACTURE: DEFINE THE CROSS-ROD CONSTRUCTION/BORE FIT",
        "  AND DEFINE HUB-TO-ARBOR TORQUE DRIVE AND AXIAL RETENTION.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
