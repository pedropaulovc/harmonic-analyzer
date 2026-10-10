r"""Magnifying-wheel dimensional contract -- the single source of truth shared by
the part build (``build_mg_magnifying_wheel.py``) and its manufacturing drawing
(``draw_mg_magnifying_wheel.py``).

PURE DATA, no SolidWorks/COM imports.  The wheel nominals live in the drawing-
FREE ``mg_magnifying_wheel_geom`` module (the assembly imports the hub
stations); they are re-exported here for the drawing-side consumers and the
offline lockstep test, which asserts the part marks and the drawing keeps
EXACTLY ``DRAWING_DIMENSIONS``.

The walls and the groove seat are proved here, not in the geom: each term
takes the band its dimension PRINTS -- its explicit model band, or the title
block's row for the places ``DRAWING_PRECISION`` gives it -- so the proof and
the sheet have one source.
"""

from __future__ import annotations

import itertools
import math

from _printed_tolerance import angular_band_deg, printed_band_mm
from mg_magnifying_wheel_geom import (  # noqa: F401 (re-export)
    BORE_BAND,
    BORE_DIA,
    GROOVE_BOTTOM_BAND,
    GROOVE_BOTTOM_DIA,
    GROOVE_R,
    GROOVE_R_BAND,
    HUB_DIA,
    HUB_DIA_BAND,
    HUB_FILLET_R,
    PEN_WIRE_DIA,
    RIM_AXIAL,
    RIM_FILLET_R,
    RIM_INNER_DIA,
    RIM_OUTER_DIA,
    SPIGOT_BAND,
    SPIGOT_DIA,
    SPOKE_AXIAL,
    SPOKE_COUNT,
    SPOKE_ROOT_WIDTH,
    SPOKE_TIP_WIDTH,
    TIE1_CLOCK_DEG,
    TIE1_R,
    TIE2_CLOCK_DEG,
    TIE_HOLE_BAND,
    TIE_HOLE_DIA,
    TIE_POSITION_TOL,
    clock_to_local_deg,
    fillet,
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

# --- walls and the groove seat at the worst PRINTED band (rule 12) -----------------
MIN_WALL = 2.0  # drawing-simplicity rule 12 target
_PLACES = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}


def _printed(model: float, name: str) -> tuple[float, float]:
    """(min, max) of a dimension that prints the title block's general row."""
    band = printed_band_mm(_PLACES[name])
    return model - band, model + band


_RIM_OD = _printed(RIM_OUTER_DIA, "RimOuterDiaDim")
_RIM_ID = _printed(RIM_INNER_DIA, "RimInnerDiaDim")
_ROOT = _printed(SPOKE_ROOT_WIDTH, "SpokeRootWidth")
_TIP = _printed(SPOKE_TIP_WIDTH, "SpokeTipWidth")
_HUB_FILLET = _printed(HUB_FILLET_R, "HubFilletR")
_RIM_FILLET = _printed(RIM_FILLET_R, "RimFilletR")
# The rim's axial width is a sheet dimension; the coarsest row bounds it.
_RIM_AXIAL_MIN = RIM_AXIAL - printed_band_mm(1)
_HUB_DIA = (HUB_DIA + HUB_DIA_BAND[1], HUB_DIA + HUB_DIA_BAND[0])
_TIE_R_MAX = (TIE_HOLE_DIA + TIE_HOLE_BAND[0]) / 2.0 + TIE_POSITION_TOL
_SPOKE_PITCH = 360.0 / SPOKE_COUNT

# TIE 1 to the boss OD (12.45 - 9.85 - 0.575 = 2.025).
TIE1_HUB_WALL = _HUB_DIA[0] / 2.0 - TIE1_R - _TIE_R_MAX
# TIE 1 to the nearest hub-fillet foot: the hole sits midway between two
# spokes, at +30 deg from the seed (+X) spoke in its frame.
_TIE1_OFF = math.radians(
    (clock_to_local_deg(TIE1_CLOCK_DEG) % _SPOKE_PITCH) or _SPOKE_PITCH
)
if abs(math.degrees(_TIE1_OFF) - _SPOKE_PITCH / 2.0) > 1e-9:
    raise AssertionError("TIE 1 must sit midway between two spokes")
_TIE1_XY = (TIE1_R * math.cos(_TIE1_OFF), TIE1_R * math.sin(_TIE1_OFF))
TIE1_FILLET_WALL = (
    min(
        math.dist(fillet(hub / 2.0, r, True, root, tip)["on_circle"], _TIE1_XY)
        for hub, r, root, tip in itertools.product(_HUB_DIA, _HUB_FILLET, _ROOT, _TIP)
    )
    - _TIE_R_MAX
)
# TIE 1 to the bore it runs beside.
TIE1_BORE_WALL = TIE1_R - _TIE_R_MAX - (BORE_DIA + BORE_BAND[0]) / 2.0
# TIE 2 to the nearest rim-fillet foot, where the hole breaks out at the rim
# ID: its angle off the nearest spoke, less the printed angular band.
_tie2_local = clock_to_local_deg(TIE2_CLOCK_DEG)
_TIE2_OFF = (
    min(
        abs((_tie2_local - k * _SPOKE_PITCH + 180.0) % 360.0 - 180.0)
        for k in range(SPOKE_COUNT)
    )
    - angular_band_deg()
)


def _tie2_to_foot(rim_id: float, r: float, root: float, tip: float) -> float:
    foot = fillet(rim_id / 2.0, r, False, root, tip)["on_circle"]
    angle = math.radians(_TIE2_OFF) - math.atan2(foot[1], foot[0])
    return rim_id / 2.0 * math.sin(angle)


TIE2_SPOKE_WALL = (
    min(
        _tie2_to_foot(*corner)
        for corner in itertools.product(_RIM_ID, _RIM_FILLET, _ROOT, _TIP)
    )
    - _TIE_R_MAX
)
# TIE 2 to the rim's side faces.
TIE2_FACE_WALL = _RIM_AXIAL_MIN / 2.0 - _TIE_R_MAX
# Spigot to bore, and the groove floor to the rim ID.
SPIGOT_WALL = (SPIGOT_DIA + SPIGOT_BAND[1] - BORE_DIA - BORE_BAND[0]) / 2.0
GROOVE_FLOOR_WALL = (GROOVE_BOTTOM_DIA + GROOVE_BOTTOM_BAND[1] - _RIM_ID[1]) / 2.0

WALLS = {
    "tie1_to_hub_od": TIE1_HUB_WALL,  # 2.025
    "tie1_to_hub_fillet": TIE1_FILLET_WALL,  # 2.088
    "tie1_to_bore": TIE1_BORE_WALL,  # 6.870
    "tie2_to_rim_fillet": TIE2_SPOKE_WALL,  # 2.706
    "tie2_to_rim_faces": TIE2_FACE_WALL,  # 3.025
    "spigot_to_bore": SPIGOT_WALL,  # 4.854
    "groove_floor": GROOVE_FLOOR_WALL,  # 4.350
}
for _name, _wall in WALLS.items():
    if _wall < MIN_WALL:
        raise AssertionError(f"wheel wall {_name} {_wall:.3f} < {MIN_WALL}")

# The pen wire seats in the groove at every printed corner: the narrowest
# groove is wider than the wire, the shallowest buries it below the rim OD,
# and the round bottom is never deeper than the groove.
GROOVE_WIDTH_MIN = 2.0 * (GROOVE_R + GROOVE_R_BAND[1])  # 1.0
GROOVE_DEPTH_MIN = (
    _RIM_OD[0] - (GROOVE_BOTTOM_DIA + GROOVE_BOTTOM_BAND[0])
) / 2.0  # 0.895
if not GROOVE_WIDTH_MIN > PEN_WIRE_DIA:
    raise AssertionError(f"groove {GROOVE_WIDTH_MIN:.3f} wide pinches the wire")
if not GROOVE_DEPTH_MIN >= PEN_WIRE_DIA:
    raise AssertionError(f"groove {GROOVE_DEPTH_MIN:.3f} deep leaves the wire proud")
if not GROOVE_DEPTH_MIN > GROOVE_R + GROOVE_R_BAND[0]:
    raise AssertionError("the groove's round bottom outgrows its depth")
