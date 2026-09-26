"""Fixed world-placement contract for the rocker-arm support casting."""

from __future__ import annotations

from _hole_spec import FRACTIONAL_DRILL_MM, HoleSpec
from cone_pivot_post_installation import ROCKER_SUPPORT_Z


# The casting's section (local frame, as build_rocker_arm_support draws it:
# Y = height with the foot at -HALF_Y, Z = wall thickness). Pure data so the
# base, frame and drive train read the foot and wall without importing the
# COM build script -- a window or rail edit there re-keys none of them.
WIDE = 31.75  # foot half-width (local Z) at y = -HALF_Y
NARROW = 8.4665  # top half-width (local Z) at y = +HALF_Y
HALF_Y = 88.9  # trapezoid half-height (local Y)
FOOT_THICKNESS = 6.35  # the foot plate under the window; the base seats key on it
HOLE_SPEC = HoleSpec("drilled_fractional", "5/16")  # 4x top-down foot clearances
HOLE_DIA = FRACTIONAL_DRILL_MM[HOLE_SPEC.size]

SUPPORT_WORLD_X = 72.9
SUPPORT_WORLD_SEAT_Y = 139.7
SUPPORT_WORLD_Z = ROCKER_SUPPORT_Z
SUPPORT_HALF_MACHINE_Z = 88.9

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
