r"""Pure-data dimensional contract for the rocker pivot bracket (MHA-123).

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

from _hole_spec import HoleSpec, blind_cut_dia_mm

FOOT_W = 16.0  # X, across the support apex (16.933 wide; 0.47 margin each side)
FOOT_H = 6.0
EAR_W = 14.0  # X
EAR_T = 6.0  # Z; the ear's Z band is the bore's (z -3..+3)
FOOT_Z0 = -EAR_T / 2.0  # foot starts at the ear's outer face ...
FOOT_Z1 = 21.0  # ... and runs 24 along +Z (inboard once placed)
FOOT_LEN = FOOT_Z1 - FOOT_Z0  # 24
BORE_H = 25.2  # shaft axis above the seat: the rocker pivot stays at machine
# y 253.8 on the 228.6 support apex
BORE_DIA = 6.5  # O6.35 shaft, 0.15 diametral clearance
EAR_ARCH_R = EAR_W / 2.0  # the ear's top is a half-round about the bore
EAR_TOP_Y = BORE_H + EAR_ARCH_R
BORE_LIGAMENT = EAR_ARCH_R - BORE_DIA / 2.0  # 3.75: rule 12 web over the bore
HOLD_DOWN_HOLE_SPEC = HoleSpec("drilled_number", "#19")
HOLE_DIA = blind_cut_dia_mm(HOLD_DOWN_HOLE_SPEC)
HOLE_Z = (9.0, 17.0)  # hold-down holes on x = 0, inside the foot's free run

if BORE_LIGAMENT < 2.0:
    raise AssertionError("ear arch leaves less than the 2.0 web over the bore")
if not all(FOOT_Z0 + HOLE_DIA / 2.0 < z < FOOT_Z1 - HOLE_DIA / 2.0 for z in HOLE_Z):
    raise AssertionError("hold-down holes must lie within the foot")
if HOLE_Z[0] - HOLE_DIA / 2.0 < EAR_T / 2.0 + 0.5:
    raise AssertionError("first hold-down hole runs under the ear")
