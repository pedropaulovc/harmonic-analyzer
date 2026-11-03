r"""MHA-CH-08 on both sides: one bracket, placed south and north.

PURE DATA, no SolidWorks/COM imports. ``build_ch_pivot_bracket`` authors the
one bracket from it, the support's seat layout and the channel assembly place
it on each side from it, and the bracket's S4 fixture sizes its ledge from
it. Kept apart from ``ch_pivot_bracket_spec`` because it reads the bank
layout, which itself imports that spec for the ear.

Both brackets keep their ears at ``rocker_bank_layout.PIVOT_BRACKET_Z`` and
turn their feet OUTBOARD, away from the rocker stack (user-approved sketch,
2026-10-09): the south bracket is placed Ry180 (part +Z -> machine -Z), the
north one IDENTITY. The ears sit 0.8 apart from mid-support, so the two
support end faces lie at different distances from them; one part serves both
sides (#1341, option A): its foot ``FOOT_Z1`` ends at the nearer end face --
the south one -- its length taken down to the printed .XX grid, and short of
the north one. The bracket has one MHA-CH-VN-57 hold-down hole in its foot's
free run from the ear's outboard face to the foot end, its station
``HOLE_Z`` given at the title block's .XX from the ear's inboard face, the
face fit-up sets (``ch_pivot_bracket_spec`` holds the bands). The hole lies in
both sides' windows between two worst-case limits -- the screw head clear of
the ear's outboard face, and the support's transferred seat keeping its wall
to the support's end face -- mid-window, its station rounded to the printed
.XX grid. The support's length is the fr part's own; this module proves the
foot fits it.
"""

from __future__ import annotations

import math

import _config
import ch_pivot_bracket_spec as _bracket
from _hole_spec import THREAD_MAJOR_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from fr_rocker_arm_support_spec import SUPPORT_HALF_MACHINE_Z, SUPPORT_WORLD_Z
from rocker_bank_layout import PIVOT_BRACKET_Z, STACK_MID_Z
from ch_vn_bracket_hold_down_screw_spec import HEAD_DIA as SCREW_HEAD_DIA
from ch_vn_bracket_hold_down_screw_spec import THREAD as SCREW_THREAD

SIDES = ("S", "N")  # south first, as PIVOT_BRACKET_Z
MOUNT_Z = dict(zip(SIDES, PIVOT_BRACKET_Z, strict=True))
# +1 where the part's +Z (its foot) runs toward machine +Z.
OUTBOARD_SIGN = {
    name: (1.0 if mount_z > STACK_MID_Z else -1.0) for name, mount_z in MOUNT_Z.items()
}

# The support (MHA-FR-05) prints on its own sheet: its length's .XX band and
# its rule-17 wall target are its unit's (rocker_bracket_seat_layout reads
# both from here).
SUPPORT_UNIT = drawing_unit(
    "parts/fr-rocker-arm-support", _config.parts("fr-rocker-arm-support")
)
SUPPORT_LENGTH_BAND = printed_band_mm(2, unit=SUPPORT_UNIT)
SUPPORT_WALL_TARGET = 2.0
SUPPORT_LENGTH = 2.0 * SUPPORT_HALF_MACHINE_Z
# The bracket's foot length and hold-down station print at .XX inch.
_GRID_MM = 25.4 / 100.0


def _support_end_z(length: float) -> dict[str, float]:
    """The support's end face on each side, in the part frame placed there,
    for a support ``length`` long (centred on SUPPORT_WORLD_Z)."""
    return {
        name: length / 2.0 + OUTBOARD_SIGN[name] * (SUPPORT_WORLD_Z - mount_z)
        for name, mount_z in MOUNT_Z.items()
    }


# The hole's window (part z). Low limit: the screw head touches the ear's
# outboard face at the worst case of the ear-thickness and station bands
# (``head_to_ear_face_min`` = 0). High limit: the seat's thread keeps the
# support's end wall when the support's end face moves by half its length's
# .X band and the hole by its station band, on whichever side that end face
# is nearer.
HOLE_Z_MIN = (
    _bracket.EAR_T / 2.0
    + SCREW_HEAD_DIA / 2.0
    + _bracket.EAR_T_BAND
    + _bracket.STATION_BAND
)


def _hole_z_max(support_end_z: float) -> float:
    return (
        support_end_z
        - SUPPORT_WALL_TARGET
        - THREAD_MAJOR_MM[SCREW_THREAD] / 2.0
        - _bracket.STATION_BAND
        - SUPPORT_LENGTH_BAND / 2.0
    )


# The printed hold-down station from the ear's inboard face, .49: a plain
# .XX nominal for a clearance hole (#1371 review), held fixed so a support
# length change moves neither this hole, its sheet nor the frame's seat
# holes. The window checks below guard it.
HOLE_STATION = 49 * _GRID_MM


def _foot_z1(support_end_z: float) -> float:
    """The foot end: the nearer support end face, its length from the ear's
    inboard face taken down to the .XX grid so it never overhangs."""
    steps = math.floor((support_end_z - _bracket.FOOT_Z0) / _GRID_MM + 1e-9)
    return _bracket.FOOT_Z0 + steps * _GRID_MM


def _foot_fits(length: float) -> bool:
    """A foot at the nearer end face of a support ``length`` long takes its
    hold-down hole inside the window with the wall target to the foot end."""
    support_end_z = min(_support_end_z(length).values())
    hole_z = _bracket.FOOT_Z0 + HOLE_STATION
    return (
        HOLE_Z_MIN <= hole_z <= _hole_z_max(support_end_z)
        and _bracket.hole_ligaments_min(hole_z, _foot_z1(support_end_z))["foot end"]
        >= _bracket.LIGAMENT_TARGET
    )


# The support's length (its own spec's; user ruling 2026-10-14 on the #954
# machinist review grew it for this foot at the millimetre bands) must give
# the foot a hold-down hole keeping the wall target to the foot end, the head
# clear of the ear and the seat's end wall.
if not _foot_fits(SUPPORT_LENGTH):
    raise AssertionError(
        f"the rocker-arm support's {SUPPORT_LENGTH:.1f} length leaves the"
        " pivot-bracket foot no hold-down station keeping its walls"
    )
SUPPORT_END_Z = _support_end_z(SUPPORT_LENGTH)  # S 13.73, N 15.34
_NEAR_END_Z = min(SUPPORT_END_Z.values())
FOOT_Z1 = _foot_z1(_NEAR_END_Z)
FOOT_LEN = FOOT_Z1 - _bracket.FOOT_Z0  # .70
HOLE_Z_MAX = _hole_z_max(_NEAR_END_Z)
if HOLE_Z_MAX <= HOLE_Z_MIN:
    raise AssertionError(
        "the foot has no hold-down station clearing both the ear and the"
        f" seat's end wall ({HOLE_Z_MIN:.2f} .. {HOLE_Z_MAX:.2f})"
    )
HOLE_Z = _bracket.FOOT_Z0 + HOLE_STATION
HOLE_MACHINE_Z = {name: MOUNT_Z[name] + OUTBOARD_SIGN[name] * HOLE_Z for name in SIDES}

HOLE_LIGAMENTS_MIN = _bracket.hole_ligaments_min(HOLE_Z, FOOT_Z1)
HEAD_TO_EAR_FACE_MIN = _bracket.head_to_ear_face_min(HOLE_Z, SCREW_HEAD_DIA)
if not HOLE_Z_MIN <= HOLE_Z <= HOLE_Z_MAX:
    raise AssertionError(
        f"the hold-down hole at {HOLE_Z:.2f} left its window"
        f" ({HOLE_Z_MIN:.2f} .. {HOLE_Z_MAX:.2f})"
    )

if sorted(OUTBOARD_SIGN.values()) != [-1.0, 1.0]:
    raise AssertionError("the two brackets must sit either side of the rocker stack")
if not _bracket.EAR_T / 2.0 + _bracket.HOLE_DIA / 2.0 < HOLE_Z < FOOT_Z1:
    raise AssertionError("the hold-down hole must lie in the foot's free run")
for _where, _ligament in HOLE_LIGAMENTS_MIN.items():
    if _ligament < _bracket.LIGAMENT_FLOOR:
        raise AssertionError(
            f"the hold-down hole leaves {_ligament:.2f} to the {_where} at worst"
            f" case, under the {_bracket.LIGAMENT_FLOOR} floor"
        )
if HOLE_LIGAMENTS_MIN["foot end"] < _bracket.LIGAMENT_TARGET:
    raise AssertionError(
        f"the hold-down hole leaves {HOLE_LIGAMENTS_MIN['foot end']:.2f} to the"
        f" foot end at worst case, under the {_bracket.LIGAMENT_TARGET} target"
    )
# The fillister head must seat on the foot clear of the ear at the worst case
# of the bands.
if HEAD_TO_EAR_FACE_MIN <= 0.0:
    raise AssertionError(
        "the hold-down screw head reaches the ear face at worst case"
        f" ({HEAD_TO_EAR_FACE_MIN:.2f})"
    )
