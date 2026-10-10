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
ears sit 1.7 apart from mid-support, so the two feet differ in length: the
configurations ``S`` and ``N`` carry their own foot end ``FOOT_Z1`` and hole
station ``HOLE_Z`` (part frame). Each bracket has one MHA-VN-032 hold-down
hole, centred in its foot's free run from the ear's outboard face to the foot
end, its station printed at .XX from the free end.
"""

from __future__ import annotations

import ch_pivot_bracket_spec as _bracket
from fr_rocker_arm_support_spec import SUPPORT_HALF_MACHINE_Z, SUPPORT_WORLD_Z
from rocker_bank_layout import PIVOT_BRACKET_Z, STACK_MID_Z
from vn_pedestal_hold_down_screw_spec import HEAD_DIA as SCREW_HEAD_DIA

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
}  # S 12.64, N 14.34
FOOT_LEN = {name: z1 - _bracket.FOOT_Z0 for name, z1 in FOOT_Z1.items()}  # 15.64, 17.34
HOLE_Z = {name: (_bracket.EAR_T / 2.0 + z1) / 2.0 for name, z1 in FOOT_Z1.items()}
# The printed station: the hole from the foot's free end (S 4.82, N 5.67).
HOLE_STATION_FROM_END = {name: FOOT_Z1[name] - HOLE_Z[name] for name in CONFIGURATIONS}
HOLE_MACHINE_Z = {
    name: MOUNT_Z[name] + OUTBOARD_SIGN[name] * HOLE_Z[name] for name in CONFIGURATIONS
}
CONFIGURATION_NUMBER = {name: f"{PART_NUMBER}-{name}" for name in CONFIGURATIONS}

# Named exception: MHA-CH-008 S end ligament (drawing-simplicity-policy.md, "Named exceptions").
# The south foot's free run is only 9.64, so its centred
# hole keeps 2.53 to the foot end nominal and 1.47 at the worst case of the
# printed bands, under the 1.5 floor: the user accepted a 1.4 floor for this
# one ligament (2026-10-09 sketch review). Every other ligament keeps 1.5.
LIGAMENT_FLOOR = {
    (name, where): (
        1.4 if (name, where) == ("S", "foot end") else _bracket.LIGAMENT_FLOOR
    )
    for name in CONFIGURATIONS
    for where in ("foot end", "foot side")
}
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
        if _ligament < LIGAMENT_FLOOR[_name, _where]:
            raise AssertionError(
                f"{_name} hold-down hole leaves {_ligament:.2f} to the {_where} at worst"
                f" case, under the {LIGAMENT_FLOOR[_name, _where]} floor"
            )
    _end_nominal = FOOT_Z1[_name] - HOLE_Z[_name] - _bracket.HOLE_DIA / 2.0
    if _end_nominal < _bracket.LIGAMENT_TARGET:
        raise AssertionError(
            f"{_name} hold-down hole leaves {_end_nominal:.2f} to the foot end, under the"
            f" {_bracket.LIGAMENT_TARGET} target"
        )
    # The fillister head must seat on the foot clear of the ear at the worst
    # case of the printed bands.
    if HEAD_TO_EAR_FACE_MIN[_name] <= 0.0:
        raise AssertionError(
            f"{_name} hold-down screw head reaches the ear face at worst case"
            f" ({HEAD_TO_EAR_FACE_MIN[_name]:.2f})"
        )
