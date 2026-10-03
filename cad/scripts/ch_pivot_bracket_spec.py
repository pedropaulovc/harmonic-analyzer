r"""Pure-data dimensional contract for the rocker pivot bracket (MHA-CH-008).

PURE DATA, no SolidWorks/COM imports: ``build_pivot_bracket`` builds from it,
and ``rocker_bank_layout`` / the channel assembly read the ear and foot from
it without importing a COM build script.

Part frame: seat face at y = 0, origin under the bore on the seat plane. The
foot runs FOOT_Z0..FOOT_Z1 along Z (the ear end at -EAR_T/2, the free end
inboard once placed); the ear is EAR_W wide (X) by EAR_T thick (Z), centred
on the origin, rising from the foot top and ARCHED with radius EAR_W/2 about
the O BORE_DIA cross-bore (#743 Q4 Reading 1: the ear carries the shaft's
shoulder, so the old brazed-on pivot ball is gone).
"""

from __future__ import annotations

import math

from _hole_spec import HoleSpec, blind_cut_dia_mm

FOOT_W = 16.0  # X, across the support apex (16.933 wide; 0.47 margin each side)
FOOT_H = 6.0
EAR_W = 14.0  # X
EAR_T = 6.0  # Z; the ear's Z band is the bore's (z -3..+3)
FOOT_Z0 = -EAR_T / 2.0  # foot starts at the ear's outer face ...
# ... and runs 24.2 along +Z (inboard once placed): 24.0 left the hold-down
# holes' end ligaments 1.456 at the printed bands (Codex #936
# PRRT_kwDOPHDy386mV3AN); the stations stay at .X and the foot grows instead.
FOOT_Z1 = 21.2
FOOT_LEN = FOOT_Z1 - FOOT_Z0  # 24.2
BORE_H = 25.2  # shaft axis above the seat: the rocker pivot stays at machine
# y 253.8 on the 228.6 support apex
BORE_DIA = 6.5  # O6.35 shaft, 0.15 diametral clearance
EAR_ARCH_R = EAR_W / 2.0  # the ear's top is a half-round about the bore
EAR_TOP_Y = BORE_H + EAR_ARCH_R
BORE_LIGAMENT = EAR_ARCH_R - BORE_DIA / 2.0  # 3.75: rule 12 web over the bore
# The MHA-VN-032 hold-downs pass here: #8 close clearance, the hole MHA-DT-002
# gives the same screw. The old #19 (0.025 radial over the thread major)
# caught the screw's under-head junction fillet on its mouth (r743-3C).
HOLD_DOWN_HOLE_SPEC = HoleSpec("clearance", "#8", fit="close")
HOLE_DIA = blind_cut_dia_mm(HOLD_DOWN_HOLE_SPEC)

# The two hold-down holes sit on x = 0 in the foot's free run, from the ear's
# inboard face to the foot end. Worst case is each term at its OWN printed
# band (Codex #936 PRRT_kwDOPHDy386mV3AN): the foot's edges at .XX (the band
# rocker_bracket_seat_layout carries this foot at), the hole stations at .X
# (they print at the step they are chosen on), and a drilled hole grows by the
# title block's +0.10/0. An edge ligament loses an edge band, a station band
# and half the drill growth; the web between the holes two station bands and
# the whole growth.
EDGE_BAND = 0.508  # title-block .XX
STATION_BAND = 0.8  # title-block .X
DRILL_GROWTH = 0.10  # title-block drilled hole, +0.10/0 on the diameter
LIGAMENT_FLOOR = 1.5
LIGAMENT_TARGET = 2.0
PRINT_STEP = 0.1  # the hole stations print at .X
FREE_RUN = (EAR_T / 2.0, FOOT_Z1)


def hole_ligaments_min(
    hole_z: tuple[float, float], run: tuple[float, float] = FREE_RUN
) -> dict[str, float]:
    """Worst-case ligament round the hold-down holes at stations hole_z."""
    edge_loss = EDGE_BAND + STATION_BAND + DRILL_GROWTH / 2.0
    return {
        "ear face": hole_z[0] - HOLE_DIA / 2.0 - run[0] - edge_loss,
        "foot end": run[1] - hole_z[1] - HOLE_DIA / 2.0 - edge_loss,
        "foot side": (FOOT_W - HOLE_DIA) / 2.0 - edge_loss,
        "between holes": hole_z[1]
        - hole_z[0]
        - HOLE_DIA
        - 2.0 * STATION_BAND
        - DRILL_GROWTH,
    }


def _stations(half_pitch: float) -> tuple[float, float]:
    mid = sum(FREE_RUN) / 2.0
    return (round(mid - half_pitch, 6), round(mid + half_pitch, 6))


# Centred on the free run, so the ear and end ligaments are equal; the pitch
# balances them against the web (run - p - d)/2 - (e + s + g/2) =
# p - d - 2s - g, which maximises the least worst-case ligament. The
# half-pitch rounds to the print step whichever way keeps that least ligament
# larger: (8.2, 16.0).
_BALANCED_PITCH = (
    FREE_RUN[1]
    - FREE_RUN[0]
    + HOLE_DIA
    - 2.0 * EDGE_BAND
    + 2.0 * STATION_BAND
    + DRILL_GROWTH
) / 3.0
_HALF_STEPS = _BALANCED_PITCH / 2.0 / PRINT_STEP
HOLE_Z = max(
    (
        _stations(round(math.floor(_HALF_STEPS) * PRINT_STEP, 6)),
        _stations(round(math.ceil(_HALF_STEPS) * PRINT_STEP, 6)),
    ),
    key=lambda hole_z: min(hole_ligaments_min(hole_z).values()),
)
HOLE_LIGAMENTS_MIN = hole_ligaments_min(HOLE_Z)
if BORE_LIGAMENT < 2.0:
    raise AssertionError("ear arch leaves less than the 2.0 web over the bore")
if not all(FOOT_Z0 + HOLE_DIA / 2.0 < z < FOOT_Z1 - HOLE_DIA / 2.0 for z in HOLE_Z):
    raise AssertionError("hold-down holes must lie within the foot")
if HOLE_Z[0] - HOLE_DIA / 2.0 < EAR_T / 2.0 + 0.5:
    raise AssertionError("first hold-down hole runs under the ear")
for _where, _ligament in HOLE_LIGAMENTS_MIN.items():
    if _ligament < LIGAMENT_FLOOR:
        raise AssertionError(
            f"hold-down hole leaves {_ligament:.2f} to the {_where} at worst case,"
            f" under the {LIGAMENT_FLOOR} floor"
        )
for _where, _nominal in (
    ("ear face", HOLE_Z[0] - HOLE_DIA / 2.0 - FREE_RUN[0]),
    ("foot end", FREE_RUN[1] - HOLE_Z[1] - HOLE_DIA / 2.0),
):
    if _nominal < LIGAMENT_TARGET:
        raise AssertionError(
            f"hold-down hole leaves {_nominal:.2f} to the {_where}, under the"
            f" {LIGAMENT_TARGET} target"
        )

