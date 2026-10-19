"""Fixed world-placement contract for the rocker-arm support casting."""

from __future__ import annotations

from _hole_spec import FRACTIONAL_DRILL_MM, HoleSpec
from _cone_axis_constants import ROCKER_SUPPORT_Z


# The casting's section lives in fr_rocker_arm_support_section_spec. The foot
# clearances stay here, with the hold-down pattern they are drilled on: the
# base and frame read both as one interface.
HOLE_SPEC = HoleSpec("drilled_fractional", "5/16")  # 4x top-down foot clearances
HOLE_DIA = FRACTIONAL_DRILL_MM[HOLE_SPEC.size]

SUPPORT_WORLD_X = 72.9
SUPPORT_WORLD_SEAT_Y = 139.7
SUPPORT_WORLD_Z = ROCKER_SUPPORT_Z
# Half the casting's length along machine Z: 180.5, the source's 7 in widened
# by 1.35 an end so the MHA-CH-08 feet, flush with its south end face, keep
# their hold-down hole's 2.0 end wall, head clearance and seat wall at
# title-block bands on the foot length and hole station
# (ch_pivot_bracket_sides derives and checks it; user ruling 2026-10-14,
# #1371 machinist review).
SUPPORT_HALF_MACHINE_Z = 90.25

# The casting's four 5/16 foot clearances are fixed in its local frame. Turning
# it +90 degrees about machine Y maps local +/-60.32 to machine Z and local
# +/-17.46 to machine X. The casting remains at its original world station;
# base and frame import this one transformed pattern.
HOLD_DOWN_LOCAL_HALF_X = 60.32
HOLD_DOWN_LOCAL_HALF_Z = 17.46
SUPPORT_HOLD_DOWN_XZ = (
    (
        SUPPORT_WORLD_X - HOLD_DOWN_LOCAL_HALF_Z,
        SUPPORT_WORLD_Z + HOLD_DOWN_LOCAL_HALF_X,
    ),
    (
        SUPPORT_WORLD_X - HOLD_DOWN_LOCAL_HALF_Z,
        SUPPORT_WORLD_Z - HOLD_DOWN_LOCAL_HALF_X,
    ),
    (
        SUPPORT_WORLD_X + HOLD_DOWN_LOCAL_HALF_Z,
        SUPPORT_WORLD_Z + HOLD_DOWN_LOCAL_HALF_X,
    ),
    (
        SUPPORT_WORLD_X + HOLD_DOWN_LOCAL_HALF_Z,
        SUPPORT_WORLD_Z - HOLD_DOWN_LOCAL_HALF_X,
    ),
)
