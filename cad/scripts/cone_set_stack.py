"""Cone-to-drum centres with the swing set by feel at assembly.

Owner direction 2026-11-11 (#2365), superseding the feeler sets of user
ruling 2026-10-10 and owner ruling 2026-11-08 for this setting: the cone set
is swung in and out by the operator many times and is locked by feel where
the gears do not bind. Assembly order (the assembly drawing's CHECKS note):
arbor-pedestal screws snug-loose, swing the set in until a gear just binds
and hold it there, tap each pedestal in or out until the gears at its end
just bind, tighten the pedestals, then swing in until a gear just binds,
ease out in small steps and stop at the first free run, and lock
the cone-lock-knob (MHA-DT-VN-51). Nothing is gauged, so no setting
reading is booked.

The ease out of the bind (check 5A) is neither printed nor measured, and no
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
the other pairs run. Check 4 lays the arbor line on a bind near each end of
the set, and the gate below takes every pair to lie between the two pairs
that hold it, none held further above standard than the highest first bind
of any pair (``SET_OFFSET_MAX_MM``). That is an assumption, not a guarantee:
the holding pairs are wherever the binds fall, and a gear past a hold lies on
the line's extension, higher by the line's slope times its overhang. Its
function (gears that do not come loose) was ruled on #2584 (owner ruling
2026-11-14, option A: accepted and stated on the sheet, exception DT-08 in
assemblies/dt-drive-train.yaml); no allowance is booked for it here.

What acts after the set (owner ruling 2026-11-24, audit part 2 P1: "A. Yes;
what is left after the setting may be combined by root sum square, with the
plain sum printed beside it; runouts of gears turning at different speeds
still add."; tolerance-policy.md, "Checks in spec modules and tests", basis
after_setting). The set itself is not a term: ``SET_OFFSET_MAX_MM`` is where
it leaves a pair at that pair's tightest phase. Three things then open the
pair's centre, none of which the swing can see:

* the running runout, ``running_runout_span_mm``: the drum
  ``TOOTH_RUNOUT_TIR_MM`` about its bore and twice the cone gear's
  eccentricity about the set's running axis (``cone_eccentricity_mm``,
  MHA-DT-04's journal to MHA-DT-37's pivot). The cone and the drum turn at
  different speeds, so their far phases meet: the two add, as one term;
* the cone gear's seat float, ``seat_float_mm``: a keyed gear rides the mesh
  load to the far side of land 1 in running, but only the pair that holds
  the line had its float taken up at the set. The holder may be a bonded tip
  gear, which has no float, so a keyed gear runs looser by its whole radial
  float (``CONE_SEAT_FLOAT_MM``). A bonded gear's float is in its
  eccentricity (it cures off its seat), so it books none here;
* the drum gear's seat float: every drum floats on MHA-DT-13, so a pair runs
  looser than the holder by the spread of the drum floats
  (``DRUM_SEAT_FLOAT_SPREAD_MM``).

Their sizes are independent: the gate takes their root sum square
(``after_set_opening_mm``) and reports the plain sum beside it
(``after_set_opening_plain_mm``); ``ConeCentre`` carries both ceilings. The
pivot's translation and the arbor's float in its pedestals move every pair
alike, so the set takes them up. The floats enter at the analysis bands of
the reamed bores and their lands (gear_seat_fit, dt_cylinder_gear_spec):
turning land 1 last to the reamed gears narrows them, and the check does not
count on it.

T024 and MHA-DT-37's pivot are each tapped true on an indicator while the
LOCTITE 638 is wet (#3292, #2473) to their sheet 16 limit, the value booked
as their reading below; T012 and T018 are not set, and their booked .0030 is
the analysis figure that check 5C's running test alone accepts. After cure
the readings are a record only (owner ruling 2026-11-24, audit part 2 C5:
"B. Keep the wet tap-true steps; the after-cure readings become a record
only; strip and re-bond only if a gear hesitates in the 80-turn running
check."): what the compound does as it cures is not booked, and MHA-DT-00
check 5C's running turns are its acceptance. A bonded gear that hesitates
there is stripped and re-bonded (2H); a keyed one, not bonded, is checked
to its sheet, remade if it fails, and the cone redone (3P-3S; delegated
ruling 2026-11-24 (Main), no precedent; owner review #2144).

The journal's axis is not the running axis (#2473, cone_running_axis):
MHA-DT-37's spigot cures off-centre and tilted in MHA-DT-04's socket, so its
pivot sits off MHA-DT-04's axis and MHA-DT-04 wobbles about the
journal-to-pivot line. MHA-DT-00 taps the pivot true, MHA-DT-04 turning in a
V-block on its journal, before the post is assembled
(``PIVOT_RUNOUT_TIR_MM``); half that reading reaches each gear by its plane's
share of the journal-to-pivot span. The terms of one gear's eccentricity
turn together and are taken at the same phase. T006 has no reading (#971):
it books its printed runout and MHA-DT-37's tilt in the socket. Not booked,
because MHA-DT-04 prints no runout of land 1 to its journal: that runout,
under the keyed gears. Owner ruling 2026-11-24 on #3402: "Route note only
(rough the journal in the same chucking as the land, dial it true in the
4-jaw before finishing); no reading." The route rides MHA-DT-04's traveler.

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
import cone_running_axis
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
# reamed pivot bore with the plate at check 5's feel-set pose, then spotted,
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
# T012/T018 print their tooth-space runout to the bore, read with a pin in
# every space, on the MHA-DT-03 sheet. Owner ruling 2026-11-21 (Pedro),
# #3219: "option D. Print the tooth-space runout to the bore (.0015 TIR, pin
# in the bore, as on MHA-PD-06) on T012 and T018, and the traveler turns the
# OD and reams the bore in the same chucking before the teeth are cut."
# It is the part's own acceptance; the mesh gate books the assembled reading
# below, which contains it.
SPIGOT_TOOTH_SPACE_RUNOUT_TIR_MM = 0.0015 * 25.4


def cone_tooth_runout_tir_mm(teeth: int) -> float:
    """Cone ``teeth``'s tooth runout about its bore, as its sheet prints it."""
    if teeth in cone.SPIGOT_TEETH:
        return SPIGOT_TOOTH_SPACE_RUNOUT_TIR_MM
    return TOOTH_RUNOUT_TIR_MM


# T024 is tapped true on land 2 while its LOCTITE 638 is wet, reading its
# tooth runout about MHA-DT-04 (MHA-DT-00 sheet 16). Owner ruling 2026-11-21
# (Pedro), #3292: "options 2 + 4 together. At assembly, while the LOCTITE 638
# is wet, indicate T024 teeth on the shaft and tap it central, then cure; the
# assembly sheet gets a check after cure: tooth runout about the shaft .0045
# TIR max. No part change." The after-cure reading is a record since the
# owner's C5 ruling of 2026-11-24 (module docstring); the limit is the wet
# setting's.
LAND_2_ASSEMBLED_RUNOUT_TIR_MM = 0.0045 * 25.4
# MHA-DT-37's bare pivot, read over a full turn with MHA-DT-04 in the V-block
# before the post is assembled (MHA-DT-00 sheet 16). Owner ruling 2026-11-22
# (Pedro), #2473, option G: "one reading remains: the pivot, .0025 TIR max in
# the V-block after cure and before the post is assembled, with a step that
# taps the pivot true while the adhesive is wet." The limit, same day, after
# T012 fell under the gate at .0025 with the spigot at its least engagement:
# "pivot .0020 TIR MAX, booked at the least spigot engagement (worst case)".
# Since C5 (2026-11-24) it is the wet tap-true's limit; after cure, a record.
PIVOT_RUNOUT_TIR_MM = 0.0020 * 25.4
# T012 and T018, recorded in the pivot's setup (MHA-DT-00 sheet 16, RECORD
# EACH SPACE). The pivot's reading does not see MHA-DT-04's socket standing
# off its journal, which tilts MHA-DT-37 with the pivot true (Codjiflo review
# of #3374: .00034 in TIR of it took T012 under the gate). Owner ruling
# 2026-11-22 (Pedro), #2473: "Add an after-cure reading of the 12- and
# 18-tooth gears in the same setup: Ø.040 pin in each tooth space, shaft on
# end on the V-block, .0030 TIR MAX (as the 24-tooth already has)". Since C5
# (2026-11-24) that reading is a record, and no step sets or checks T012 or
# T018 to .0030 (1S taps only T024, 2B only the pivot): the .0030 is the
# booked analysis figure, accepted only by check 5C's running test.
SPIGOT_ASSEMBLED_RUNOUT_TIR_MM = 0.0030 * 25.4
# Read about MHA-DT-04's journal: gear -> its TIR limit.
ASSEMBLED_RUNOUT_TIR_MM = {
    **{teeth: LAND_2_ASSEMBLED_RUNOUT_TIR_MM for teeth in cone.LAND_2_TEETH},
    **{teeth: SPIGOT_ASSEMBLED_RUNOUT_TIR_MM for teeth in cone.SPIGOT_TEETH},
}


def bond_float_mm(teeth: int) -> float:
    """How far a bonded cone gear's bore can cure off its seat: half its own
    bond clearance; zero for the keyed gears, whose float is
    ``seat_float_mm``.  dt_cone_gear_tl_phasing_comb_spec.BOND_FLOAT_MM is a
    different quantity: one common float, the largest of these and the
    spigot's half clearance in MHA-DT-04's socket, about T030's key rather
    than the axis."""
    if teeth in cone.ROUND_BORE_TEETH:
        return cone.bond_clearance_mm(teeth)[1] / 2.0
    return 0.0


def seat_eccentricity_mm(teeth: int) -> float:
    """The largest eccentricity of cone ``teeth``'s teeth about the axis it
    is accepted on: MHA-DT-04's journal for the gears read after cure, its
    own seat (MHA-DT-04's land, or MHA-DT-37 for T006) for the rest."""
    if teeth in ASSEMBLED_RUNOUT_TIR_MM:
        return ASSEMBLED_RUNOUT_TIR_MM[teeth] / 2.0
    return cone_tooth_runout_tir_mm(teeth) / 2.0 + bond_float_mm(teeth)


def cone_eccentricity_mm(teeth: int) -> float:
    """The largest eccentricity of cone ``teeth``'s teeth about the running
    axis: about the axis it is accepted on, plus that axis's own offset from
    the running axis with the pivot at its read limit."""
    pivot_offset = PIVOT_RUNOUT_TIR_MM / 2.0
    if teeth in ASSEMBLED_RUNOUT_TIR_MM:
        axis_offset = cone_running_axis.journal_axis_offset_mm(teeth, pivot_offset)
    else:
        axis_offset = cone_running_axis.seat_offset_mm(teeth, pivot_offset)
    return seat_eccentricity_mm(teeth) + axis_offset


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
# The spread of the drum gears' radial floats on MHA-DT-13: the most a pair's
# drum floats beyond the holding pair's.
DRUM_SEAT_FLOAT_SPREAD_MM = (DRUM_SEAT_CLEARANCE[1] - DRUM_SEAT_CLEARANCE[0]) / 2.0

# The not-coming-loose gate: nominal contact ratio at the loosest running
# centre after the set (dt_mesh_checks.cone_check; checks/cone-set-stack.yaml).
# Delegated ruling 2026-11-12 (Main), following the owner's direction of
# 2026-11-11 on #2416 (module docstring).  T006 is exempt (#971).
NOMINAL_CONTACT_RATIO_MIN = 1.0


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


# The highest first bind of any pair: check 4 lays the arbor line on a bind
# near each end and check 5 swings the set in to the first bind.  Every pair
# taken to lie between the pairs that hold the line sits no higher than this
# at its tightest phase; a gear past a hold is accepted by the owner's #2584
# ruling (option A, exception DT-08; see the module docstring).
SET_OFFSET_MAX_MM = max(max(first_bind_offsets_mm(t)) for t in cone.CONE_TEETH)


def running_runout_span_mm(teeth: int) -> float:
    """The far phase of the running runout: the set is felt at the tightest
    phase of a full turn, and the cone's eccentricity and the drum's (TIR / 2)
    each open the centre by twice their size at the opposite phase.  The two
    gears turn at different speeds, so the far phases meet and the two add."""
    return 2.0 * cone_eccentricity_mm(teeth) + TOOTH_RUNOUT_TIR_MM


def seat_float_mm(teeth: int) -> float:
    """How much looser than the holding pair cone ``teeth``'s own seat float
    runs it: a keyed gear's whole radial float on land 1 (the holder may be a
    bonded gear, with none); nothing for a bonded gear or T006, whose float
    is in ``cone_eccentricity_mm``."""
    return CONE_SEAT_FLOAT_MM if teeth in cone.KEYED_TEETH else 0.0


def after_set_terms_mm(teeth: int) -> tuple[float, float, float]:
    """What opens cone ``teeth``'s centre past where the set leaves it:
    (running runout, cone seat float, drum seat float spread), in mm."""
    return running_runout_span_mm(teeth), seat_float_mm(teeth), DRUM_SEAT_FLOAT_SPREAD_MM


def after_set_opening_mm(teeth: int) -> float:
    """The gated opening: the root sum square of the independent terms (owner
    ruling 2026-11-24, audit part 2 P1)."""
    return math.hypot(*after_set_terms_mm(teeth))


def after_set_opening_plain_mm(teeth: int) -> float:
    """The plain sum of the same terms, reported beside the gated opening."""
    return sum(after_set_terms_mm(teeth))


@dataclass(frozen=True)
class ConeCentre:
    """The centres a feel set can leave cone ``teeth`` at, in mm."""

    teeth: int
    floor_mm: float  # its own least first bind: never tighter, at any phase
    set_max_mm: float  # the loosest the set holds it, at its tightest phase
    ceiling_mm: float  # set_max_mm opened by the root sum square after the set
    ceiling_plain_mm: float  # REF: set_max_mm opened by the plain sum

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
        set_max + after_set_opening_mm(teeth),
        set_max + after_set_opening_plain_mm(teeth),
    )


# The T120 centre's largest departure from the CAD placement under a feel
# set: the swing's angle error at T120.  The bore centres sit at the
# effective (tooth-contact) bind on the tight side and up to one TIR above it
# on the loose side, where the two eccentricities point at each other.
SWING_SET_FROM_PLACEMENT_MM = max(
    abs(min(first_bind_offsets_mm(120)) - SET_ABOVE_STANDARD_MM),
    abs(SET_OFFSET_MAX_MM + TOOTH_RUNOUT_TIR_MM - SET_ABOVE_STANDARD_MM),
)
