"""World-placement contract for the unmodified rocker-arm support casting."""

from __future__ import annotations

from cone_pivot_post_installation import ROCKER_SUPPORT_Z


SUPPORT_WORLD_X = 72.9
SUPPORT_WORLD_SEAT_Y = 139.7
SUPPORT_WORLD_Z = ROCKER_SUPPORT_Z
SUPPORT_HALF_MACHINE_Z = 88.9

# The casting's four 9/16-12 foot taps are fixed in its local frame.  Turning
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


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "support mounting-seat flatness": "0.10",
    "support hole-pattern position": "0.40",
}
