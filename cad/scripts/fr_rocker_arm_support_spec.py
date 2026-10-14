"""Fixed world-placement contract for the rocker-arm support casting."""

from __future__ import annotations

from _hole_spec import FRACTIONAL_DRILL_MM, HoleSpec
from _inch import inch
from dt_cone_pivot_post_installation import ROCKER_SUPPORT_Z


# The casting's section lives in fr_rocker_arm_support_section_spec. The foot
# clearances stay here, with the hold-down pattern they are drilled on: the
# base and frame read both as one interface.
HOLE_SPEC = HoleSpec("drilled_fractional", "5/16")  # 4x top-down foot clearances
HOLE_DIA = FRACTIONAL_DRILL_MM[HOLE_SPEC.size]

# Rocker pivot (2-7/8, 10 in): agreed with the rocker bracket seat layout.
SUPPORT_WORLD_X = inch(2.875)  # 73.025 (was 72.9)
SUPPORT_WORLD_SEAT_Y = inch(5.5)  # 139.7: base top 2 in + half-height 3-1/2 in
SUPPORT_WORLD_Z = ROCKER_SUPPORT_Z
SUPPORT_HALF_MACHINE_Z = inch(3.5)  # 88.9: half the 7 in wall (local X)

# The casting's four 5/16 foot clearances are fixed in its local frame. Turning
# it +90 degrees about machine Y maps local +/-2-3/8 in to machine Z and local
# +/-11/16 in to machine X. The casting remains at its original world station;
# base and frame import this one transformed pattern.
HOLD_DOWN_LOCAL_HALF_X = inch(2.375)  # 60.325 (was 60.32)
HOLD_DOWN_LOCAL_HALF_Z = inch(11, 16)  # 17.4625 (was 17.46)
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
