r"""Pure-data dimensional contract for the rocker pivot bracket (MHA-CH-008).

PURE DATA, no SolidWorks/COM imports: ``build_ch_pivot_bracket`` builds from it,
and ``rocker_bank_layout`` / the channel assembly read the ear and foot from
it without importing a COM build script.

Part frame: seat face at y = 0, origin under the bore on the seat plane. The
foot runs FOOT_Z0 along +Z (the ear end at -EAR_T/2, the free end outboard
once placed, flush with the support's end face); the ear is EAR_W wide (X) by
EAR_T thick (Z), centred on the origin, rising from the foot top and ARCHED
with radius EAR_W/2 about the O BORE_DIA cross-bore (#743 Q4 Reading 1: the
ear carries the shaft's shoulder, so the old brazed-on pivot ball is gone).
The ear is as wide as the foot, so their sides are one flat each side.

The foot's end and its one hold-down hole depend on which end of the support
the bracket sits at, so they are per configuration: ``ch_pivot_bracket_sides``
derives them from the bank layout (which imports this module for the ear, so
the derivation cannot live here) and checks them with the ligament functions
below.
"""

from __future__ import annotations

from _hole_spec import HoleSpec, blind_cut_dia_mm

FOOT_W = 16.0  # X, across the support apex (16.933 wide; 0.47 margin each side)
FOOT_H = 6.0
EAR_W = FOOT_W  # X: the ear's sides run flush with the foot's
EAR_T = 6.0  # Z; the ear's Z band is the bore's (z -3..+3)
FOOT_Z0 = -EAR_T / 2.0  # foot starts at the ear's inboard face
BORE_H = 25.2  # shaft axis above the seat: the rocker pivot stays at machine
# y 253.8 on the 228.6 support apex
BORE_DIA = 6.5  # O6.35 shaft, 0.15 diametral clearance
EAR_ARCH_R = EAR_W / 2.0  # the ear's top is a half-round about the bore
EAR_TOP_Y = BORE_H + EAR_ARCH_R  # 33.2
BORE_LIGAMENT = EAR_ARCH_R - BORE_DIA / 2.0  # 4.75: rule 12 web over the bore
# The MHA-VN-032 hold-down passes here: #8 close clearance, the hole MHA-DT-002
# gives the same screw. The old #19 (0.025 radial over the thread major)
# caught the screw's under-head junction fillet on its mouth (r743-3C).
HOLD_DOWN_HOLE_SPEC = HoleSpec("clearance", "#8", fit="close")
HOLE_DIA = blind_cut_dia_mm(HOLD_DOWN_HOLE_SPEC)

# One hold-down hole per bracket, on x = 0 in the foot's free run (from the
# ear's outboard face to the foot end), its station printed at .XX from the
# foot's free end. Worst case is each term at its OWN printed band (Codex #936
# PRRT_kwDOPHDy386mV3AN): the foot's edges at .XX (the band
# rocker_bracket_seat_layout carries this foot at), the hole station at .XX,
# and a drilled hole grows by the title block's +0.10/0. An edge ligament
# loses an edge band, a station band and half the drill growth.
EDGE_BAND = 0.508  # title-block .XX
STATION_BAND = 0.508  # title-block .XX
DRILL_GROWTH = 0.10  # title-block drilled hole, +0.10/0 on the diameter
LIGAMENT_FLOOR = 1.5
LIGAMENT_TARGET = 2.0
EDGE_LOSS = EDGE_BAND + STATION_BAND + DRILL_GROWTH / 2.0


def hole_ligaments_min(hole_z: float, foot_z1: float) -> dict[str, float]:
    """Worst-case ligaments round a hold-down hole at station hole_z.

    The ear face is no free edge (the foot runs on under the ear), so the
    hole's run-side limit is the screw head's clearance to it, not a ligament:
    see ``head_to_ear_face_min``.
    """
    return {
        "foot end": foot_z1 - hole_z - HOLE_DIA / 2.0 - EDGE_LOSS,
        "foot side": (FOOT_W - HOLE_DIA) / 2.0 - EDGE_LOSS,
    }


def head_to_ear_face_min(hole_z: float, head_dia: float) -> float:
    """Worst-case gap from the hold-down screw's head to the ear's outboard face.

    The station is printed from the foot's free end, so the ear face moves
    against it by the foot's edge band and the station's own band.
    """
    return hole_z - head_dia / 2.0 - EAR_T / 2.0 - EDGE_BAND - STATION_BAND


if BORE_LIGAMENT < 2.0:
    raise AssertionError("ear arch leaves less than the 2.0 web over the bore")
