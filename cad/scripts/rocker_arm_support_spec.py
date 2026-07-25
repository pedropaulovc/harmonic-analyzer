"""Cross-subassembly clearance contract for the rocker-arm support.

The frame fixes the support at this machine transform.  The v2 cone-post
cascade moved the alignment-pinion pivot rig into the support's lower north
corner, so the source-replayed casting receives three small, machined clearance
features.  Their bounds are the measured p2 envelopes expanded by 0.25 mm.

Keep this module geometry-only: the support part, frame assembly, and drive
assembly all import it, so a future cascade must satisfy one shared contract.
"""

from __future__ import annotations

import math

SUPPORT_WORLD_X = 72.9
SUPPORT_WORLD_SEAT_Y = 139.7
SUPPORT_WORLD_Z = 0.0
SUPPORT_HALF_MACHINE_Z = 88.9

P2_CLEARANCE = 0.25

# Back pivot block plus its two #4 hold-down screws.  This pocket is open
# through the casting's low-X and north (+Z) faces.
P2_BACK_X_MAX = 46.99053046000287
P2_BACK_Y_MAX = 72.30
P2_BACK_Z_MIN = 75.75

# Brass return-spring foot: a shallow slot at the mounting-seat surface.
P2_SPRING_X_MAX = 52.08610240207359
P2_SPRING_Y_MIN = 50.55
P2_SPRING_Y_MAX = 51.85
P2_SPRING_Z_MIN = 68.70
P2_SPRING_Z_MAX = 73.20

# The spring-foot screw needs a separate vertical pocket; keeping it round
# preserves more ligament to the support's nearest 9/16-12 hold-down tap.
P2_FOOT_SCREW_X = 48.73610240207359
P2_FOOT_SCREW_Z = 70.95
P2_FOOT_SCREW_DIA = 6.00
P2_FOOT_SCREW_Y_MIN = 50.55
P2_FOOT_SCREW_Y_MAX = 54.05


def _local_x(world_z: float) -> float:
    """Machine Z -> support-local X under frame's +90 degree Y rotation."""
    return SUPPORT_WORLD_Z - world_z


def _local_y(world_y: float) -> float:
    return world_y - SUPPORT_WORLD_SEAT_Y


def _local_z(world_x: float) -> float:
    return world_x - SUPPORT_WORLD_X


P2_BACK_LOCAL_PLANE_X = _local_x(P2_BACK_Z_MIN)
P2_BACK_LOCAL_INNER_Z = _local_z(P2_BACK_X_MAX)
P2_BACK_LOCAL_TOP_Y = _local_y(P2_BACK_Y_MAX)

P2_SPRING_LOCAL_X_MIN = _local_x(P2_SPRING_Z_MAX)
P2_SPRING_LOCAL_X_MAX = _local_x(P2_SPRING_Z_MIN)
P2_SPRING_LOCAL_INNER_Z = _local_z(P2_SPRING_X_MAX)
P2_SPRING_LOCAL_Y_MIN = _local_y(P2_SPRING_Y_MIN)
P2_SPRING_LOCAL_Y_MAX = _local_y(P2_SPRING_Y_MAX)

P2_FOOT_SCREW_LOCAL_X = _local_x(P2_FOOT_SCREW_Z)
P2_FOOT_SCREW_LOCAL_Z = _local_z(P2_FOOT_SCREW_X)
P2_FOOT_SCREW_LOCAL_Y_MIN = _local_y(P2_FOOT_SCREW_Y_MIN)
P2_FOOT_SCREW_LOCAL_Y_MAX = _local_y(P2_FOOT_SCREW_Y_MAX)

# Source-replayed support tap nearest the p2 relief, transformed to machine X/Z.
_NEAREST_TAP_X = SUPPORT_WORLD_X - 17.46
_NEAREST_TAP_Z = 60.32
_TAP_RADIUS = 12.30376 / 2.0
P2_SPRING_SLOT_LIGAMENT = (
    math.hypot(
        _NEAREST_TAP_X - P2_SPRING_X_MAX,
        P2_SPRING_Z_MIN - _NEAREST_TAP_Z,
    )
    - _TAP_RADIUS
)
P2_FOOT_SCREW_LIGAMENT = (
    math.hypot(
        _NEAREST_TAP_X - P2_FOOT_SCREW_X,
        P2_FOOT_SCREW_Z - _NEAREST_TAP_Z,
    )
    - _TAP_RADIUS
    - P2_FOOT_SCREW_DIA / 2.0
)

if P2_SPRING_SLOT_LIGAMENT < 2.5:
    raise AssertionError("p2 spring slot leaves under 2.5 mm at the support tap")
if P2_FOOT_SCREW_LIGAMENT < 3.0:
    raise AssertionError("p2 screw pocket leaves under 3.0 mm at the support tap")


def assert_p2_envelopes(
    *,
    back_x_max: float,
    back_y_max: float,
    back_z_min: float,
    spring_x_max: float,
    spring_y_min: float,
    spring_y_max: float,
    spring_z_min: float,
    spring_z_max: float,
    foot_screw_x: float,
    foot_screw_z: float,
    foot_screw_dia: float,
    foot_screw_y_min: float,
    foot_screw_y_max: float,
) -> None:
    """Fail offline if the live p2 formulas outgrow the authored reliefs."""
    checks = (
        (back_x_max + P2_CLEARANCE, P2_BACK_X_MAX, "back pocket X"),
        (back_y_max + P2_CLEARANCE, P2_BACK_Y_MAX, "back pocket Y"),
        (P2_BACK_Z_MIN, back_z_min - P2_CLEARANCE, "back pocket Z"),
        (spring_x_max + P2_CLEARANCE, P2_SPRING_X_MAX, "spring slot X"),
        (P2_SPRING_Y_MIN, spring_y_min - P2_CLEARANCE, "spring slot low Y"),
        (spring_y_max + P2_CLEARANCE, P2_SPRING_Y_MAX, "spring slot high Y"),
        (P2_SPRING_Z_MIN, spring_z_min - P2_CLEARANCE, "spring slot low Z"),
        (spring_z_max + P2_CLEARANCE, P2_SPRING_Z_MAX, "spring slot high Z"),
        (foot_screw_x, P2_FOOT_SCREW_X, "foot-screw X"),
        (foot_screw_z, P2_FOOT_SCREW_Z, "foot-screw Z"),
        (foot_screw_dia + 2.0 * P2_CLEARANCE, P2_FOOT_SCREW_DIA, "foot-screw dia"),
        (P2_FOOT_SCREW_Y_MIN, foot_screw_y_min - P2_CLEARANCE, "foot-screw low Y"),
        (foot_screw_y_max + P2_CLEARANCE, P2_FOOT_SCREW_Y_MAX, "foot-screw high Y"),
    )
    for required, authored, label in checks:
        if abs(required - authored) > 1e-6:
            raise AssertionError(
                f"{label}: p2 envelope {required:.6f} != relief {authored:.6f}"
            )
