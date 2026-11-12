"""Cone-to-drum centres with the swing set by feel at assembly.

Owner direction 2026-11-11 (#2365), superseding the feeler sets of user
ruling 2026-10-10 and owner ruling 2026-11-08 for this setting: the cone set
is swung in and out by the operator many times and is locked by feel where
the gears do not bind. Assembly order (the assembly drawing's CHECKS note):
arbor-pedestal screws snug-loose, hold the set swung in and tap each pedestal
in until the gears at its end just bind, tighten the pedestals, then swing in
until a gear just binds, ease out only until the gears turn freely, and lock
the cone-lock-knob (MHA-DT-VN-51). Nothing is gauged, so no setting
reading is booked.

The ease out of the bind (check 4N) is neither printed nor measured, and no
number is booked for it: delegated ruling 2026-11-12 (Main), following the
owner's direction of 2026-11-11 on #2416 (the gears must not bind and must
not come loose; backlash is not a function); owner review #2144, pending
owner confirmation. An allowance for it would be an invented
number. The stack books the first bind and the real stack terms, and the
not-coming-loose gate is the nominal contact ratio there.

The swing stops where the first pair binds: its backlash closes, a tip
reaches the mate's base tangent, or a tip meets the mate's root (T006's
ground relief takes the drum tip below its base circle; its own clearance is
dt_mesh_checks.t006_relief_clearance_mm). What the feel set guarantees is the
floor: no pair runs tighter than its own first bind at its tightest phase,
so the tightest pair runs at backlash >= 0. It does not fix how much looser
the other pairs run. Check 4 lays the arbor line on the binds at both ends
of the set, so no pair is held further above standard than the highest
first bind of any pair (``SET_OFFSET_MAX_MM``); a pair then runs looser than
that at the far phase of its running runout, the cone and the drum each
``TOOTH_RUNOUT_TIR_MM`` about their bores. The seat floats, the pivot's
translation and the arbor's float are taken up the same way under the mesh
load at the set as in running, so they do not move a pair off its set.

The CAD places the cone line ``SET_ABOVE_STANDARD_MM`` above standard at
every cone; the feel set runs T120 tighter than that, by
``SWING_SET_FROM_PLACEMENT_MM`` at most, which the swing's clearance stacks
book (dt_cone_tip_air, dt_cylinder_end_disc_clearance).
"""
from __future__ import annotations

import functools
import math
from dataclasses import dataclass

from scipy.optimize import brentq

import _config
import cone_stations
import dt_arbor_pedestal_spec as pedestal
import dt_cone_gear_spec as cone
import dt_cone_swing_platform_pivot_spec as platform
import dt_cylinder_gear_shaft_spec as arbor
import dt_cylinder_gear_spec as drum
import dt_vn_cone_pivot_screw_spec as pivot_screw
from cone_pitch import SEAT_PITCH
from _cone_axis_constants import GEAR_AXIS_SHIFT
from dt_cylinder_gear_spec import BORE_DIAMETRAL_CLEARANCE_MM as DRUM_SEAT_CLEARANCE
from dt_cylinder_gear_spec import TEETH as DRUM_TEETH
from gear_seat_fit import GEAR_SEAT_CLEARANCE
from standard_mesh_checks import PlaneGear, backlash, interference_margin, plane_gear, root_clearance

SET_ABOVE_STANDARD_MM = float(_config.fit("cone_drum_oblique_mesh", "edge_slack_mm"))
# The D1 pivot seat in MHA-FR-01 is transfer-punched through MHA-DT-20's
# reamed pivot bore with the plate at check 4's feel-set pose, then spotted,
# drilled and tapped with the base still on the mill (MHA-DT-00 step 23,
# owner ruling 2026-11-08). The seat is never located from the MHA-DT-02
# pedestal seats, so it carries no band from them (#2366): it lands off the
# bore it was punched through by the punch's radial play in that bore and by
# picking the punch mark up under the spindle.
# Transfer punch: the stock 1/4 in punch, ground under by .0025 ±.0005 (Precise
# spotter sets, 2.5 mm to 17/32 in; Penn Tool listing read 2026-11-12).
TRANSFER_PUNCH_DIA_MIN_MM = (0.25 - 0.0025 - 0.0005) * 25.4
PIVOT_TRANSFER_PUNCH_PLAY_MM = (
    platform.PIVOT_HOLE_DIA + platform.PIVOT_HOLE_BAND[0] - TRANSFER_PUNCH_DIA_MIN_MM
) / 2.0
# AUTHOR'S CHOICE (#2366): centring the spindle on the punch mark to spot it,
# .002 in.
PUNCH_MARK_PICKUP_MM = 0.002 * 25.4
PIVOT_SEAT_TRANSFER_MM = PIVOT_TRANSFER_PUNCH_PLAY_MM + PUNCH_MARK_PICKUP_MM
TOOTH_RUNOUT_TIR_MM = float(
    _config.fit("cone_drum_oblique_mesh", "tooth_cutting_runout_tir_mm")
)
ALPHA_RAD = math.radians(cone.PRESSURE_ANGLE_DEG)

# The swing's own clearances, for the stacks of the parts it carries.
# ASME B1.1 #10-24 UNC: 2B internal pitch diameter max 0.1672 in, 2A external
# min 0.1586 in; the screw can centre anywhere in that radial play.
PIVOT_THREAD_CENTRING_MM = (0.1672 - 0.1586) * 25.4 / 2.0
PIVOT_BORE_FLOAT_MM = (
    platform.PIVOT_HOLE_DIA + platform.PIVOT_HOLE_BAND[0]
    - (pivot_screw.SHOULDER_DIA + pivot_screw.SHOULDER_DIA_BAND[1])
) / 2.0
ARBOR_RUNNING_FLOAT_MM = (
    pedestal.BORE_DIA + pedestal.BORE_DIA_BAND[0] - (arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[1])
) / 2.0
CONE_SEAT_FLOAT_MM = GEAR_SEAT_CLEARANCE[1] / 2.0
DRUM_SEAT_FLOAT_MM = DRUM_SEAT_CLEARANCE[1] / 2.0


def pivot_distance_mm(teeth: int) -> float:
    """Pivot to cone ``teeth``'s mesh station along the cone line."""
    if teeth % 6 or not 6 <= teeth <= 120:
        raise ValueError(f"no cone T{teeth:03d}")
    j = (120 - teeth) // 6
    return cone_stations.PIVOT_STATION - (
        cone_stations.SHAFT_T120_STATION + GEAR_AXIS_SHIFT + j * SEAT_PITCH
    )


def standard_centre_mm(teeth: int) -> float:
    return (teeth + DRUM_TEETH) * cone.MODULE_MM / 2.0


@functools.cache
def drum_corners() -> tuple[PlaneGear, ...]:
    """The drum's four printed OD/thickness corners in the check plane."""
    return tuple(plane_gear(p, drum.MODULE_MM) for p in drum.manufacturing_corner_profiles())


@functools.cache
def cone_corners(teeth: int) -> tuple[PlaneGear, ...]:
    """Cone ``teeth``'s four printed OD/thickness corners in the check plane."""
    return tuple(plane_gear(p, cone.MODULE_MM) for p in cone.manufacturing_corner_profiles(teeth))


def _closes_at_mm(contact, a: PlaneGear, b: PlaneGear) -> float:
    """The centre at which ``contact`` (a clearance, closing as the centre
    falls) reaches zero, or the base-circle sum if it is still open there."""
    base = (a.pitch_radius + b.pitch_radius) * math.cos(ALPHA_RAD)
    low, high = base * 1.0001, base * 1.2
    if contact(low) >= 0.0:
        return low
    if contact(high) <= 0.0:
        raise ValueError("a cone pair is closed at every centre searched")
    return brentq(contact, low, high, xtol=1e-9)


def first_bind_mm(a: PlaneGear, b: PlaneGear, *, relieved: bool = False) -> float:
    """The least centre at which cone ``a`` runs on drum ``b`` without
    binding: its backlash closes, a tip reaches the mate's base tangent, or
    a tip meets the mate's root, whichever comes first as the swing comes in.
    A ``relieved`` cone (T006) takes the drum tip below its base circle on
    its ground relief, so the tangent limit is not its."""
    contacts = [
        lambda c: backlash(a, b, c, ALPHA_RAD),
        lambda c: root_clearance(a, b, c),
    ]
    if not relieved:
        contacts.append(lambda c: interference_margin(a, b, c, ALPHA_RAD))
    return max(_closes_at_mm(contact, a, b) for contact in contacts)


@functools.cache
def first_bind_offsets_mm(teeth: int) -> tuple[float, ...]:
    """Each printed corner pair's first bind, as its centre above standard."""
    std = standard_centre_mm(teeth)
    return tuple(
        first_bind_mm(a, b, relieved=teeth == 6) - std
        for a in cone_corners(teeth)
        for b in drum_corners()
    )


# The highest first bind of any pair: check 4 taps each pedestal in to the
# first bind at its end and swings the set in to the first bind, easing out
# only until the gears turn, so the arbor line lies on the binds at both ends
# and every pair lies between the pairs that hold the swing, none above this
# at its tightest phase.
SET_OFFSET_MAX_MM = max(max(first_bind_offsets_mm(t)) for t in cone.CONE_TEETH)
# The far phase of the running runout: the set is felt at the tightest phase
# of a full turn, and the cone's and the drum's eccentricities (TIR/2 each)
# open the centre by up to 2 x TIR at the opposite phase.
RUNNING_RUNOUT_SPAN_MM = 2.0 * TOOTH_RUNOUT_TIR_MM


@dataclass(frozen=True)
class ConeCentre:
    """The centres a feel set can leave cone ``teeth`` at, in mm."""

    teeth: int
    floor_mm: float  # its own least first bind: never tighter, at any phase
    set_max_mm: float  # the loosest the set holds it, at its tightest phase
    ceiling_mm: float  # set_max_mm at the far phase of its running runout

    @property
    def range_mm(self) -> tuple[float, float]:
        return self.floor_mm, self.ceiling_mm


def cone_centre(teeth: int) -> ConeCentre:
    std = standard_centre_mm(teeth)
    set_max = std + SET_OFFSET_MAX_MM
    return ConeCentre(
        teeth,
        std + min(first_bind_offsets_mm(teeth)),
        set_max,
        set_max + RUNNING_RUNOUT_SPAN_MM,
    )


# The T120 centre's largest departure from the CAD placement under a feel
# set: the swing's angle error at T120.  The bore centres sit at the
# effective (tooth-contact) bind on the tight side and up to one TIR above it
# on the loose side, where the two eccentricities point at each other.
SWING_SET_FROM_PLACEMENT_MM = max(
    abs(min(first_bind_offsets_mm(120)) - SET_ABOVE_STANDARD_MM),
    abs(SET_OFFSET_MAX_MM + TOOTH_RUNOUT_TIR_MM - SET_ABOVE_STANDARD_MM),
)
