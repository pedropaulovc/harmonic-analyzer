r"""Magnifying-wheel dimensional contract -- the single source of truth shared by
the part build (``build_mg_magnifying_wheel.py``) and its manufacturing drawing
(``draw_mg_magnifying_wheel.py``).

PURE DATA, no SolidWorks/COM imports.  The wheel nominals live in the drawing-
FREE ``mg_magnifying_wheel_geom`` module (the assembly imports the hub
stations); they are re-exported here for the drawing-side consumers and the
offline lockstep test, which asserts the part marks and the drawing keeps
EXACTLY ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from mg_magnifying_wheel_geom import (  # noqa: F401 (re-export)
    BORE_DIA,
    HUB_DIA,
    RIM_AXIAL,
    RIM_INNER_DIA,
    RIM_OUTER_DIA,
    SPOKE_AXIAL,
    SPOKE_COUNT,
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The face view carries the rim, bore, spoke, fillet and tie
# dimensions; the side view carries the hub profile, the groove and the spoke
# thickness.  The rim's axial width is added on the sheet. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RimProfile": {"RimOuterDiaDim", "RimInnerDiaDim"},
    "SpokeProfile": {"SpokeRootWidth", "SpokeTipWidth"},
    "Spoke": {"SpokeAxial"},
    "HubProfile": {"HubDia", "SpigotDia", "HubLength", "SpigotLength", "HubBackZ"},
    "BoreProfile": {"BoreDiaDim"},
    "HubFillets": {"HubFilletR"},
    "RimFillets": {"RimFilletR"},
    "GrooveProfile": {"GrooveR", "GrooveBottomDia"},
    "Tie1Profile": {"Tie1Y", "Tie1HoleDia"},
    "Tie2Profile": {"Tie2HoleDia", "Tie2Angle"},
}
# Decimal places per marked dimension (drawing-simplicity rule 2): the cast
# shapes at one place, the turned and drilled sizes at two, the press-fit
# spigot and the reamed bore at three.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RimProfile": {"RimOuterDiaDim": 2, "RimInnerDiaDim": 1},
    "SpokeProfile": {"SpokeRootWidth": 1, "SpokeTipWidth": 1},
    "Spoke": {"SpokeAxial": 1},
    "HubProfile": {
        "HubDia": 2,
        "SpigotDia": 3,
        "HubLength": 2,
        "SpigotLength": 2,
        "HubBackZ": 2,
    },
    "BoreProfile": {"BoreDiaDim": 3},
    "HubFillets": {"HubFilletR": 1},
    "RimFillets": {"RimFilletR": 1},
    "GrooveProfile": {"GrooveR": 2, "GrooveBottomDia": 2},
    "Tie1Profile": {"Tie1Y": 2, "Tie1HoleDia": 2},
    "Tie2Profile": {"Tie2HoleDia": 2, "Tie2Angle": 0},
}

DRAWING_NOTES = "\n".join(
    (
        f"{SPOKE_COUNT} TAPERED CAST SPOKES, EQUALLY SPACED.",
        "TIE 1: LEVER-WIRE TIE HOLE THROUGH THE BOSS.",
        "TIE 2: PEN-WIRE TIE HOLE, GROOVE BOTTOM TO RIM BORE.",
        "BORE REAMED; RUNS ON THE MG-WHEEL-AXLE.",
    )
)
# The right view is a plain side elevation (hidden lines), NOT a cutting-plane
# section -- labelled honestly so the sheet does not promise section geometry it
# does not carry.
SECTION_VIEW_NOTE = "SIDE VIEW SCALE 1:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
