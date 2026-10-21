r"""Summing-lever dimensional contract -- the single source of truth shared by
the part build (``build_sm_summing_lever.py``) and its manufacturing drawing
(``draw_sm_summing_lever.py``).

PURE DATA, no SolidWorks/COM imports (``stock_anchor_geom`` is pure geometry).
A large green-iron casting: a coefficients plate carrying the 20 channel-spring
anchor taps on the +X arm, a solid pivot cylinder with hex knife-edge
trunnions, and a curved summation arm ending in the tapped counter-spring
anchor boss on the -X arm.  Both anchors are purchased eyebolts that thread
straight into those taps -- the lever IS their nut -- so this module owns the
two thread identities and the boss height, and no plain anchor bore exists.
Values MUST match build_sm_summing_lever.py.
"""

from __future__ import annotations

import math
from _hole_spec import HoleSpec
from stock_anchor_geom import ANCHOR_9489T111, ANCHOR_9490T1


from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

MM_PER_IN = 25.4

# --- Nominal geometry (SummingLever.cs, inches -> mm; DIMENSIONS.md ch. 18). ---
PLATE_W = 1.75 * MM_PER_IN  # 44.45 coefficients-plate width (X)
PLATE_L = 6.0 * MM_PER_IN  # 152.40 plate / pivot length (Z)
PLATE_T = 0.2 * MM_PER_IN  # 5.08 plate thickness
CYL_R = 0.5 * MM_PER_IN  # 12.70 pivot-cylinder radius
SUM_H = 3.0 * MM_PER_IN  # 76.20 summation reach (-X)
ANCHOR_R = 0.375 * MM_PER_IN  # 9.525 summation-anchor outer radius
ANCHOR_H = 0.75 * MM_PER_IN  # 19.05 summation-anchor boss height (Y)

# hex knife-edge trunnion (vertex-up).  HEX_W was 8.653 (118.6 deg ridge);
# narrowed to 8.080 (115.1 deg ridge) so the trunnion still rocks >= 5.0 deg
# inside the sm-knife-mount Ø12 close bore at the worst case of BOTH parts'
# bands (``build_sm_summing_assembly.KNIFE_FREE_ROCK_WORST_DEG``).  The print
# holds the ridge to each side face and each upper flank to its side face
# (below); the width prints as a reference, the vertex height .XXX at HEX_BAND.
HEX_W = 8.080
HEX_H = 10.268
HEX_BAND = 0.13  # title-block .XXX band on HEX_H
HEX_DEPTH = 21.717
# Included angle of the knife-edge ridge (the top vertex of the hexagon).
RIDGE_ANGLE_DEG = 2.0 * math.degrees(math.atan2(HEX_W / 2.0, HEX_H / 4.0))
# Each ridge is truncated by a small round (drawing-guidelines rule 16; owner
# ruling 2026-10-16: the user's ask timed out and the recommended option was
# auto-selected), modelled at its printed limit, R0.1 MAX; HEX_H stays the
# theoretical sharp the print dimensions.  KNIFE_RIDGE_TANGENT_XY is the
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
# flank's own angle free; one flank could take the whole angle band.  Detail D
# instead holds, on both stubs, the ridge sharp RIDGE_FROM_SIDE from EACH side
# face and each upper flank KNIFE_FLANK_TO_SIDE_DEG to its side face, both
# toleranced explicitly; HexWidth becomes a reference.  The worst shoulder is
# the farthest from the ridge with the flattest flank: KNIFE_SHOULDER_X_MAX
# out and KNIFE_SHOULDER_DROP_MIN down, on a flank KNIFE_FLANK_HALF_MAX_DEG
# off the vertical.  The edge's hardness is still unspecified (#1611).
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
# Between the stubs: both are one prism through the body
# (``build_sm_summing_lever._hex_knife``, read back by
# ``_assert_knife_sides_coplanar``), so each side face of one stub lies in the
# same plane as the other's, and the print says so ("SIDES IN ONE PLANE").
# Each ridge then stands RIDGE_FROM_SIDE +/-RIDGE_FROM_SIDE_TOL from the SAME
# side plane, which puts the two ridges within KNIFE_STUB_RIDGE_OFFSET_MAX of
# each other.  This bound rests on the shared planes: with each stub's sides
# free, the symmetry would tie each ridge only to its own stub, and nothing
# would tie the -Z ridge to datum A.  The two ridges rest on the knife mounts
# at the stubs' mid-lengths, KNIFE_RIDGE_CONTACT_SPAN apart, so that offset
# skews the knife axis and spreads the 20 spring holes' hook arms by up to
# KNIFE_HOOK_ARM_SPREAD_MAX over the column.
KNIFE_STUB_RIDGE_OFFSET_MAX = 2.0 * RIDGE_FROM_SIDE_TOL  # 0.10
KNIFE_RIDGE_CONTACT_SPAN = PLATE_L + HEX_DEPTH  # 174.117 stub mid to stub mid

# Outward normal and plane offset of the upper-right sloping face of the
# vertex-up hexagon. Its upper endpoint is the +Y knife-edge ridge.
_KNIFE_FACE_SCALE = math.hypot(HEX_H / 4.0, HEX_W / 2.0)
KNIFE_FACE_NORMAL = (
    (HEX_H / 4.0) / _KNIFE_FACE_SCALE,
    (HEX_W / 2.0) / _KNIFE_FACE_SCALE,
    0.0,
)
KNIFE_FACE_OFFSET = KNIFE_FACE_NORMAL[1] * HEX_H / 2.0

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "knife_edge_ridge",
        MACHINED_UM,
        PlanarFace(
            KNIFE_FACE_NORMAL,
            KNIFE_FACE_OFFSET,
            contains_z_mm=(PLATE_L + HEX_DEPTH) / 2.0,
        ),
    ),
)

# The 20 channel-spring lower anchors (McMaster 9489T111, part ``ch-vn-spring-hook``)
# thread DIRECTLY into the coefficient plate -- the supplied nut is discarded
# and each is locked by an MHA-CH-14 jam nut on the plate underside -- so
# each station is a through tap, not a bore:
# one native seed + a linear pattern. The size is the anchor's own thread, so a
# supplier change can never leave the lever tapped for the wrong screw.
HOLE_SPEC = HoleSpec("tapped", ANCHOR_9489T111.thread_size)
HOLE_X = 39.85
HOLE_COUNT = 20
CHANNEL_Z0 = -67.1
CHANNEL_PITCH = 7.0565
# The spring stations sit on the channel arm plane, the cam plane
# (rocker_bank_layout.ARM_MID_DZ = cam_plane.CAM_MID_DZ). Restated,
# like CHANNEL_Z0/CHANNEL_PITCH, not imported: this spec is read by
# _interference_contracts, so an import would put the gear-train and channel
# config into every assembly's closure. test_sm_summing_lever_drawing pins it.
HOLE_Z_OFFSET = -3.52825
# The 5.08 plate leaves a #6-32 only 1.1D of full thread, so a continuous pad
# along the hole row's underside (owner ruling 2026-10-16, option B; the
# user's ask timed out and the recommended option was auto-selected) gives
# each tap 1.5D at the title block's .XX band
# (``sm_summing_lever_notes`` proves it).  SPRING_SEAT_T is the tap's whole
# length: plate top to pad underside, where each MHA-CH-14 jam nut seats.
# The pad runs the plate's full length and in from its free +X edge past the
# nut's O.D.
SPRING_SEAT_T = 7.0
SPRING_PAD_W = 10.0

# The sm-vn-counter-spring lower anchor (McMaster 9490T1, part ``sm-vn-boss-hook``) threads
# DIRECTLY through the summation-anchor boss on the same no-nut rule, authored
# natively AFTER the structural ribs so none of them can refill it.
COUNTER_HOLE_SPEC = HoleSpec("tapped", ANCHOR_9490T1.thread_size)

# --- Derived. ---
CYL_DIA = 2.0 * CYL_R  # 25.4
TIP_X = -SUM_H  # -76.20 summation tip / anchor X
HOLE_Z_FIRST = CHANNEL_Z0 + HOLE_Z_OFFSET
HOLE_Z_LAST = CHANNEL_Z0 + CHANNEL_PITCH * (HOLE_COUNT - 1) + HOLE_Z_OFFSET
HOLE_EDGE_OFFSET = PLATE_W - HOLE_X  # 4.60 from the free +X plate edge
HOLE_END_OFFSET_FIRST = HOLE_Z_FIRST + PLATE_L / 2.0  # from the -Z end
HOLE_END_OFFSET_LAST = PLATE_L / 2.0 - HOLE_Z_LAST  # from the +Z end
HEX_Z_INNER = PLATE_L / 2.0  # trunnion inboard face flush with the body end (76.20)
HEX_Z_OUTER = HEX_Z_INNER + HEX_DEPTH  # outboard face overhangs the body (97.92)
# The between-stub ridge offset's hook-arm spread over the hole column (0.077).
KNIFE_HOOK_ARM_SPREAD_MAX = (
    KNIFE_STUB_RIDGE_OFFSET_MAX
    * (HOLE_Z_LAST - HOLE_Z_FIRST)
    / KNIFE_RIDGE_CONTACT_SPAN
)

# Drawing prose + marked-dimension contract (DRAWING_DIMENSIONS /
# ISOMETRIC_VIEW_NOTE) live in ``sm_summing_lever_notes`` --
# ``build_sm_summing_assembly`` / ``build_sm_knife_mount`` import this module, so
# drawing-only data here would put every notes edit in their rebuild
# closures (codex #354).


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    # Ø0.15, tightened from 0.30 (owner ruling on code review
    # C06): two neighbouring MHA-CH-14 jam nuts stand on adjacent taps, and
    # at Ø0.30 their worst approach leaves no O.D. both the wall floor and the
    # 0.25 neighbour clearance admit (ch_anchor_jam_nut_spec).
    "spring-hole pattern position": "0.15",
}
