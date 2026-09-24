r"""Pure-data dimensional contract shared by the pinion strap torque shaft and
its manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A plain Ø6.35 turned steel shaft with a
shallow spherical crown at each end -- the pivot the two swing straps rock on.
The nominals drive the part's named equation globals AND the drawing's
coordinate math; the marked-dimension map keeps the part marks and the drawing
keeps in lockstep (``test_pinion_pivot_shaft_drawing.py``).
"""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_rig_layout import TORQUE_SHAFT_LEN

SHAFT_DIA = 6.35  # 1/4 in: rides both pivot blocks' east bores and the straps
# Ends flush with the pivot blocks' outer faces; ruling (c) moved the front
# block inboard to the front strap (pinion_rig_layout), 192 -> 182.0
# (the physical stack, never the model pose's air: Codex #854).
SHAFT_LEN = TORQUE_SHAFT_LEN
CAP_SAG = 1.2  # shallow spherical crown height at each end
CAP_RADIUS = ((SHAFT_DIA / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)
SHAFT_DIA_BAND = SHAFT_H
# U27 (Main, 2026-09-24): the length carries the title-block .X band (+/-0.8),
# not a tight one.  Set back-flush, the front end stands at worst 0.85 proud
# of the front block, the SR crown apex 2.05.  Nothing stands on the shaft's
# axis past either block: the nearest body, the MHA-059 lever, rides the lift
# rod 18.63 off it -- hub 8.95 radial clear, arm >= 12.42 clear over the -82
# degree throw (test_drive_train_support_layout::
# test_torque_shaft_length_band_clears_both_ends).  Each block still bears
# >= 9.5 of its 10.25.
DRAWING_PRECISION: dict[str, dict[str, int]] = {"Shaft": {"Depth": 1}}

SURFACE_FINISHES = (
    SurfaceFinishControl("bearing", MACHINED_UM, CylinderFace(SHAFT_DIA)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "CYLINDRICAL BODY HAS NO FLATS OR STEPS.",
        "DATUM A IS THE CYLINDRICAL BODY'S DERIVED AXIS.",
        "BOTH SPHERICAL CROWN SURFACES: PROFILE 0.05, FORM ONLY (NO DATUM);",
        "  EACH CROWN IS INSPECTED INDEPENDENTLY.",
        f"  SR{CAP_RADIUS:.2f}+/-0.05 GOVERNS SIZE; ({CAP_SAG:.2f}) REF AXIAL HEIGHT",
        "  FROM EACH CROWN ROOT CIRCLE.",
        "CROWN ROOT CIRCLES ARE SHARP THEORETICAL PROFILE BREAKS;",
        "  EXEMPT FROM TITLE-BLOCK EDGE-BREAK REQUIREMENT.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
# The isometric renders at ISO_SCALE (1, 2) while the sheet/title block reads
# 1:1, so without this the pictorial is silently half scale.  Mirrors
# fulcrum-shaft / cylinder-gear-shaft, whose identical 1:2 iso carry the note.
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "pinion pivot cylindrical body": "0.01",
    "pinion pivot crown profile": "0.05",
}
