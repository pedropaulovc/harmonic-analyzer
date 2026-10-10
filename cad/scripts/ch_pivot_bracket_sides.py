r"""MHA-CH-008's two configurations: the south and north pivot brackets.

PURE DATA, no SolidWorks/COM imports. ``build_ch_pivot_bracket`` authors one
configuration per side from it, the support's seat layout and the channel
assembly place them from it, and the bracket's S4 fixture sizes its ledge from
it. Kept apart from ``ch_pivot_bracket_spec`` because it reads the bank
layout, which itself imports that spec for the ear.

Both brackets keep their ears at ``rocker_bank_layout.PIVOT_BRACKET_Z`` and
turn their feet OUTBOARD, away from the rocker stack (user-approved sketch,
2026-10-09): the south bracket is placed Ry180 (part +Z -> machine -Z), the
north one IDENTITY. Each foot ends flush with the support's end face, and the
ears sit 0.8 apart from mid-support, so the two feet differ in length: the
configurations ``S`` and ``N`` carry their own foot end ``FOOT_Z1`` and hole
station ``HOLE_Z`` (part frame). Each bracket has one MHA-VN-032 hold-down
hole in its foot's free run from the ear's outboard face to the foot end,
its station given +/-0.10 from the ear's inboard face, the face fit-up sets
(``ch_pivot_bracket_spec`` holds the bands). The hole is centred in the free
run where the centre lies between its two worst-case limits -- the screw head
clear of the ear's outboard face, and the support's transferred seat keeping
its 2.0 wall to the support's end face -- as in the north foot. The south
foot's free run is short (user, 2026-10-10: 8-thick ears beside the 1/32
thrust washers), so its hole sits mid-way between the two limits instead,
off the centre toward the ear.
"""

from __future__ import annotations

import ch_pivot_bracket_spec as _bracket
from _hole_spec import THREAD_MAJOR_MM
from fr_rocker_arm_support_spec import SUPPORT_HALF_MACHINE_Z, SUPPORT_WORLD_Z
from rocker_bank_layout import PIVOT_BRACKET_Z, STACK_MID_Z
from vn_pedestal_hold_down_screw_spec import HEAD_DIA as SCREW_HEAD_DIA
from vn_pedestal_hold_down_screw_spec import THREAD as SCREW_THREAD

PART_NUMBER = "MHA-CH-008"
CONFIGURATIONS = ("S", "N")  # south first, as PIVOT_BRACKET_Z
MOUNT_Z = dict(zip(CONFIGURATIONS, PIVOT_BRACKET_Z, strict=True))
# +1 where the part's +Z (its foot) runs toward machine +Z.
OUTBOARD_SIGN = {
    name: (1.0 if mount_z > STACK_MID_Z else -1.0) for name, mount_z in MOUNT_Z.items()
}
# The foot's free end lies in the support's end face on its side.
FOOT_Z1 = {
    name: SUPPORT_HALF_MACHINE_Z + OUTBOARD_SIGN[name] * (SUPPORT_WORLD_Z - mount_z)
    for name, mount_z in MOUNT_Z.items()
}  # S 12.44, N 14.05
FOOT_LEN = {name: z1 - _bracket.FOOT_Z0 for name, z1 in FOOT_Z1.items()}  # 16.44, 18.05

# The hole's window (part z). Low limit: the screw head touches the ear's
# outboard face at the worst case of the ear-thickness and station bands
# (``head_to_ear_face_min`` = 0). High limit: the seat's thread keeps
# rocker_bracket_seat_layout's 2.0 end wall when the support's end face moves
# by half its 177.8's title-block .X band and the hole by its station band.
SUPPORT_LENGTH_BAND = 0.8  # title-block .X on the support's 177.8
HOLE_Z_MIN = (
    _bracket.EAR_T / 2.0
    + SCREW_HEAD_DIA / 2.0
    + _bracket.EAR_T_BAND
    + _bracket.STATION_BAND
)
HOLE_Z_MAX = {
    name: z1
    - _bracket.LIGAMENT_TARGET
    - THREAD_MAJOR_MM[SCREW_THREAD] / 2.0
    - _bracket.STATION_BAND
    - SUPPORT_LENGTH_BAND / 2.0
    for name, z1 in FOOT_Z1.items()
}
for _name, _z_max in HOLE_Z_MAX.items():
    if _z_max <= HOLE_Z_MIN:
        raise AssertionError(
            f"{_name} foot has no hold-down station clearing both the ear and the"
            f" seat's end wall ({HOLE_Z_MIN:.2f} .. {_z_max:.2f})"
        )
# Centred in the free run where the centre lies in the window, else
# mid-window.
_FREE_RUN_MID = {
    name: (_bracket.EAR_T / 2.0 + z1) / 2.0 for name, z1 in FOOT_Z1.items()
}
HOLE_Z = {
    name: mid
    if HOLE_Z_MIN <= mid <= HOLE_Z_MAX[name]
    else (HOLE_Z_MIN + HOLE_Z_MAX[name]) / 2.0
    for name, mid in _FREE_RUN_MID.items()
}
# The printed station: the hole from the ear's inboard face (S 11.74, N 13.02).
HOLE_STATION = {name: HOLE_Z[name] - _bracket.FOOT_Z0 for name in CONFIGURATIONS}
HOLE_MACHINE_Z = {
    name: MOUNT_Z[name] + OUTBOARD_SIGN[name] * HOLE_Z[name] for name in CONFIGURATIONS
}
CONFIGURATION_NUMBER = {name: f"{PART_NUMBER}-{name}" for name in CONFIGURATIONS}

# The south foot's free run is only 8.44: its hole keeps 2.41 to the foot end
# nominal and 2.16 at the worst case of the +/-0.10 bands.
HOLE_LIGAMENTS_MIN = {
    name: _bracket.hole_ligaments_min(HOLE_Z[name], FOOT_Z1[name])
    for name in CONFIGURATIONS
}
HEAD_TO_EAR_FACE_MIN = {
    name: _bracket.head_to_ear_face_min(HOLE_Z[name], SCREW_HEAD_DIA)
    for name in CONFIGURATIONS
}

if sorted(OUTBOARD_SIGN.values()) != [-1.0, 1.0]:
    raise AssertionError("the two brackets must sit either side of the rocker stack")
for _name in CONFIGURATIONS:
    if (
        not _bracket.EAR_T / 2.0 + _bracket.HOLE_DIA / 2.0
        < HOLE_Z[_name]
        < FOOT_Z1[_name]
    ):
        raise AssertionError(f"{_name} hold-down hole must lie in the foot's free run")
    for _where, _ligament in HOLE_LIGAMENTS_MIN[_name].items():
        if _ligament < _bracket.LIGAMENT_FLOOR:
            raise AssertionError(
                f"{_name} hold-down hole leaves {_ligament:.2f} to the {_where} at worst"
                f" case, under the {_bracket.LIGAMENT_FLOOR} floor"
            )
    _end_nominal = FOOT_Z1[_name] - HOLE_Z[_name] - _bracket.HOLE_DIA / 2.0
    if _end_nominal < _bracket.LIGAMENT_TARGET:
        raise AssertionError(
            f"{_name} hold-down hole leaves {_end_nominal:.2f} to the foot end, under the"
            f" {_bracket.LIGAMENT_TARGET} target"
        )
    # The fillister head must seat on the foot clear of the ear at the worst
    # case of the bands.
    if HEAD_TO_EAR_FACE_MIN[_name] <= 0.0:
        raise AssertionError(
            f"{_name} hold-down screw head reaches the ear face at worst case"
            f" ({HEAD_TO_EAR_FACE_MIN[_name]:.2f})"
        )
