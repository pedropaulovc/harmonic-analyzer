"""Fixed world-placement contract for the rocker-arm support casting."""

from __future__ import annotations

import _config
from _hole_spec import FRACTIONAL_DRILL_MM, HoleSpec
from _cone_axis_constants import ROCKER_SUPPORT_Z
from _package_units import drawing_unit

# The sheet prints decimal inch (issue #290, ``drawing_unit: in``).
UNIT = drawing_unit("parts/fr-rocker-arm-support", _config.parts("fr-rocker-arm-support"))


# The casting's section lives in fr_rocker_arm_support_section_spec. The foot
# clearances stay here, with the hold-down pattern they are drilled on: the
# base and frame read both as one interface.
HOLE_SPEC = HoleSpec("drilled_fractional", "5/16")  # 4x top-down foot clearances
HOLE_DIA = FRACTIONAL_DRILL_MM[HOLE_SPEC.size]

SUPPORT_WORLD_X = 72.9
SUPPORT_WORLD_SEAT_Y = 139.7
SUPPORT_WORLD_Z = ROCKER_SUPPORT_Z
# Half the casting's length along machine Z: 180.4924 (7.106), the source's
# 7 in widened by .053 an end so the MHA-CH-08 feet, flush with its south end
# face, keep their hold-down hole's end wall, head clearance and seat wall at
# title-block bands on the foot length and hole station
# (ch_pivot_bracket_sides derives and checks it; user ruling 2026-10-14,
# #1371 machinist review).
SUPPORT_HALF_MACHINE_Z = 90.2462  # 3.553

# The casting's four 5/16 foot clearances are fixed in its local frame. Turning
# it +90 degrees about machine Y maps local +/-2.375 to machine Z and local
# +/-.687 to machine X. The casting remains at its original world station;
# base and frame import this one transformed pattern.
HOLD_DOWN_LOCAL_HALF_X = 60.325  # 2.375
HOLD_DOWN_LOCAL_HALF_Z = 17.4498  # .687
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
