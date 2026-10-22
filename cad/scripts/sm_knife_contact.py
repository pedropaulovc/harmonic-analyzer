r"""Summing-lever knife contact cross-section and its printed limits.

Shared by the lever geometry, its drawing, and the mating bore's rocking proof.
Axial stub/body dimensions belong to ``sm_summing_lever_spec``; plate, rib and
anchor changes must not alter this cross-section's dependency boundary.
Pure geometry: no manufacturing helpers, configuration, or SolidWorks imports.
"""

from __future__ import annotations

import math

# Hex knife-edge trunnion (vertex-up). HEX_W was 8.653 (118.6 deg ridge);
# narrowed to 8.080 (115.1 deg ridge) so the trunnion still rocks >= 5.0 deg
# inside the sm-knife-mount Ø12 close bore at the worst case of BOTH parts'
# bands (``build_sm_summing_assembly.KNIFE_FREE_ROCK_WORST_DEG``). The print
# holds the ridge to each side face and each upper flank to its side face;
# the width prints as a reference, the vertex height .XXX at HEX_BAND.
HEX_W = 8.080
HEX_H = 10.268
HEX_BAND = 0.13  # title-block .XXX band on HEX_H
RIDGE_ANGLE_DEG = 2.0 * math.degrees(math.atan2(HEX_W / 2.0, HEX_H / 4.0))
# Each ridge is truncated by a small round (drawing-guidelines rule 16; owner
# ruling 2026-10-16: the user's ask timed out and the recommended option was
# auto-selected), modelled at its printed limit, R0.1 MAX; HEX_H stays the
# theoretical sharp the print dimensions. KNIFE_RIDGE_TANGENT_XY is the
# (x, y) of the round's +X tangent line on the upper-right face, the visible
# ridge edge the plan picks.
KNIFE_RIDGE_R = 0.1
KNIFE_RIDGE_R_BAND = (0.0, -KNIFE_RIDGE_R)  # (upper, lower)
KNIFE_RIDGE_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R0.1 MAX"
_RIDGE_HALF = math.radians(RIDGE_ANGLE_DEG) / 2.0
_RIDGE_SETBACK = KNIFE_RIDGE_R / math.tan(_RIDGE_HALF)
KNIFE_RIDGE_TANGENT_XY = (
    _RIDGE_SETBACK * math.sin(_RIDGE_HALF),
    HEX_H / 2.0 - _RIDGE_SETBACK * math.cos(_RIDGE_HALF),
)
# Code review C09 (owner ruling T1, 2026-10-17): the included angle with
# HexWidth and HexHeight left the ridge's position between the sides and each
# flank's own angle free; one flank could take the whole angle band. Detail D
# instead holds, on both stubs, the ridge sharp RIDGE_FROM_SIDE from EACH side
# face and each upper flank KNIFE_FLANK_TO_SIDE_DEG to its side face, both
# toleranced explicitly; HexWidth becomes a reference. The worst shoulder is
# the farthest from the ridge with the flattest flank: KNIFE_SHOULDER_X_MAX
# out and KNIFE_SHOULDER_DROP_MIN down, on a flank KNIFE_FLANK_HALF_MAX_DEG
# off the vertical. The edge's hardness is still unspecified (#1611).
KNIFE_FLANK_TO_SIDE_DEG = round(180.0 - RIDGE_ANGLE_DEG / 2.0, 1)  # 122.4 printed
KNIFE_FLANK_TO_SIDE_TOL_DEG = 0.5
RIDGE_FROM_SIDE = HEX_W / 2.0  # 4.040 from each side face
RIDGE_FROM_SIDE_TOL = 0.05
KNIFE_SHOULDER_X_MAX = RIDGE_FROM_SIDE + RIDGE_FROM_SIDE_TOL
KNIFE_FLANK_HALF_MAX_DEG = 180.0 - (
    KNIFE_FLANK_TO_SIDE_DEG - KNIFE_FLANK_TO_SIDE_TOL_DEG
)
KNIFE_SHOULDER_DROP_MIN = KNIFE_SHOULDER_X_MAX / math.tan(
    math.radians(KNIFE_FLANK_HALF_MAX_DEG)
)
# Both stubs' side faces are one prism's planes. Holding each ridge to those
# shared planes bounds their mutual offset; the resulting hook-arm spread
# also needs the axial contact span and hole column, owned by the lever spec.
KNIFE_STUB_RIDGE_OFFSET_MAX = 2.0 * RIDGE_FROM_SIDE_TOL  # 0.10

# Outward normal and plane offset of the upper-right sloping face of the
# vertex-up hexagon. Its upper endpoint is the +Y knife-edge ridge.
_KNIFE_FACE_SCALE = math.hypot(HEX_H / 4.0, HEX_W / 2.0)
KNIFE_FACE_NORMAL = (
    (HEX_H / 4.0) / _KNIFE_FACE_SCALE,
    (HEX_W / 2.0) / _KNIFE_FACE_SCALE,
    0.0,
)
KNIFE_FACE_OFFSET = KNIFE_FACE_NORMAL[1] * HEX_H / 2.0
