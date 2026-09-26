r"""Axial (machine-z) layout of the cylinder-gear bank and its retention
(issue #743) -- one source for the drive-train assembly, the channel cam plane
and the alignment-pinion rig's worst stacks.

GEOMETRY ONLY: no drawing notes, no annotation contract, no drawing-spec
imports, and no title-block reads (the ``pinion_rig_layout`` precedent), so a
print-wording edit can never re-key the drive train.

The bank is a SOLID STACK. Each MHA-027 gear's overall thickness, cam face to
back face, is the station pitch, so neighbouring gears bear cam face on back
face, as the rocker hubs do (``rocker_arm_spec.HUB_LENGTH``). A turned thrust
washer (MHA-121) sits at each end between the end gear and its arbor-pedestal
strap.

* The BACK (north) strap is the bank's axial datum. Its inner face is
  DRO-located at fit-up, and the bank is pushed back against it: g19's back
  face bears on the back washer, which bears on the back strap.
* The arbor fills both strap bores and domes proud of each strap; a set
  screw in each pedestal's crown apex bears on it (MHA-147): the back one
  fixes the arbor, the front one is tightened once the end-play leaf is set.
* The FRONT (south) strap is feeler-set: one BANK_END_FEELER leaf between the
  front washer and the strap. That gap is the bank's assembled end play, E_b.
  The feeler is chosen by the rule ``pinion_rig_layout`` uses for its drum
  shim: the smallest 0.05 blade whose tightest setting keeps MIN_END_PLAY with
  MARGIN_SPARE to spare.
* Every gear's overall thickness is +/-0.025 on its print (user ruling L20
  d'). A fit-up acceptance on the measured 20-gear stack (STACK_L20_ACCEPT,
  +/-0.20) caps the cumulative deviation, so g0's position relative to g19
  never carries 19 per-gear bands. A part of the stack is not capped by the
  acceptance alone: its gears may all lean one way while the rest lean the
  other (partial_stack_band).

The bank is not preloaded. So in service any one gear interface can open by up
to E_b max, and a connecting-rod ring pressed toward the gear in front of it
overhangs its cam by at most that gap (user ruling on #743, Q1: bounded
overhang accepted; RING_OVERHANG_MAX).

Stacks are dicts of named, non-negative terms, summed like
``pinion_rig_layout.DRUM_BACK_ADVANCE_STACK``. "South" is machine -z (the
front, gear 0, crank side); "north" is +z (the back, gear 19).
"""

from __future__ import annotations

import math

import _config
import arbor_pedestal_spec as _pedestal
import arbor_set_screw_spec as _screw
import connecting_rod_spec as _rod
import cylinder_gear_shaft_spec as _shaft
from cylinder_end_disc_spec import (
    WASHER_THICK,
    WASHER_THICK_TOLERANCE_MM,
)
from cylinder_gear_spec import (
    CAM_THICKNESS,
    FACE_WIDTH,
    FACE_WIDTH_TOLERANCE_MM,
    OVERALL_THICKNESS,
    OVERALL_THICKNESS_BAND,
)

COUNT = 20  # the bank is the full set of 20 cylinder gears (every build)

# --- station pitch --------------------------------------------------------
# The drive-train ladders the gears at the cone-incline z-pitch (the same
# formula as build_drive_train_assembly.Z_PITCH). The gear's printed overall
# thickness is the channel station pitch; the two agree to well under a
# micrometre per station, and the gear is never the longer of the two, so the
# modelled stack closes without interference.
_DP_TRAIN = _config.machine("gear_train", "diametral_pitch")
_RADIUS_STEP = 3.0 * 25.4 / _DP_TRAIN
_SEAT = _config.machine("cone_incline", "drum_seat_nominal_mm")
BANK_PITCH = _SEAT * math.cos(math.asin(_RADIUS_STEP / _SEAT))
STATION_Z0 = _config.machine("channels", "station_z0_mm")
PITCH_LOCKSTEP_TOLERANCE = 0.001
if not 0.0 <= BANK_PITCH - OVERALL_THICKNESS <= PITCH_LOCKSTEP_TOLERANCE:
    raise AssertionError(
        f"gear overall thickness {OVERALL_THICKNESS} is not the bank pitch "
        f"{BANK_PITCH:.6f} (0..{PITCH_LOCKSTEP_TOLERANCE})"
    )


def station_z(j: int) -> float:
    """Machine z of gear j's tooth-face mid-plane."""
    return STATION_Z0 + BANK_PITCH * j


# --- end play (E_b) ---------------------------------------------------------
MIN_END_PLAY = 0.10  # running floor for 20 oiled brass faces
MARGIN_SPARE = 0.25  # novice spare over every floor (pinion_rig_layout rule)
FEELER_STEP = 0.05  # blades of the metric gauge set (pinion_rig_fitup)
BANK_END_FEELER_BAND = 0.10  # set error: hold-down float re-set, ruled band
BANK_END_FEELER = FEELER_STEP * math.ceil(
    round((MIN_END_PLAY + MARGIN_SPARE + BANK_END_FEELER_BAND) / FEELER_STEP, 9)
)
BANK_END_PLAY = (
    BANK_END_FEELER - BANK_END_FEELER_BAND,
    BANK_END_FEELER + BANK_END_FEELER_BAND,
)
BANK_END_PLAY_TERMS = {
    "front feeler": BANK_END_FEELER,
    "feeler set error": BANK_END_FEELER_BAND,
}
# Differential expansion of the brass stack against the iron base over
# +/-15 K. Reported, not counted: it sits inside MARGIN_SPARE, as the rig's
# drum-shim rule treats it.
THERMAL_END_PLAY_DRIFT = (19e-6 - 11e-6) * OVERALL_THICKNESS * COUNT * 15.0

# --- stack length acceptance -------------------------------------------------
STACK_L20 = COUNT * OVERALL_THICKNESS  # g0 cam face to g19 back face
# (upper, lower): re-face a long stack; remake the thinnest gear of a short
# one, which no re-facing can lengthen (user ruling L20 d', #743).
STACK_L20_ACCEPT_BAND = (0.20, -0.20)
STACK_L20_ACCEPT = (
    STACK_L20 + STACK_L20_ACCEPT_BAND[1],
    STACK_L20 + STACK_L20_ACCEPT_BAND[0],
)
# Each gear's mic acceptance at fit-up, the print's band.
GEAR_THICKNESS_ACCEPT = (
    OVERALL_THICKNESS + OVERALL_THICKNESS_BAND[1],
    OVERALL_THICKNESS + OVERALL_THICKNESS_BAND[0],
)
# Was "keep T +/0: a thin gear cannot be fixed at fit-up". Under d' a thin
# gear is in band, which holds only while both bands stay centred, so an
# in-band stack sits about nominal and the acceptance rejects it either way.
# (The thinnest in-band cam must still hold the whole ring: RING_SLOT_MARGIN.)
if (
    OVERALL_THICKNESS_BAND[0] != -OVERALL_THICKNESS_BAND[1]
    or STACK_L20_ACCEPT_BAND[0] != -STACK_L20_ACCEPT_BAND[1]
):
    raise AssertionError(
        "gear thickness and 20-gear stack bands must both be centred: "
        f"T {OVERALL_THICKNESS_BAND}, L20 {STACK_L20_ACCEPT_BAND}"
    )


def partial_stack_band(n: int) -> tuple[float, float]:
    """(upper, lower) summed thickness deviation of any n gears of an
    accepted stack: each gear inside its band, all COUNT inside the
    acceptance, so the other COUNT - n may lean the opposite way."""
    upper, lower = OVERALL_THICKNESS_BAND
    accept_upper, accept_lower = STACK_L20_ACCEPT_BAND
    rest = COUNT - n
    return (
        min(n * upper, accept_upper - rest * lower),
        max(n * lower, accept_lower - rest * upper),
    )

# --- nominal stations (bank pushed back against the datum) -----------------
G19_BACK_FACE_Z = station_z(COUNT - 1) + FACE_WIDTH / 2.0
BACK_WASHER_Z = (G19_BACK_FACE_Z, G19_BACK_FACE_Z + WASHER_THICK)
BACK_STRAP_INNER_Z = BACK_WASHER_Z[1]
G0_TOOTH_FRONT_Z = station_z(0) - FACE_WIDTH / 2.0
G0_CAM_FACE_Z = station_z(0) + FACE_WIDTH / 2.0 - OVERALL_THICKNESS
FRONT_WASHER_Z = (G0_CAM_FACE_Z - WASHER_THICK, G0_CAM_FACE_Z)
FRONT_STRAP_INNER_Z = FRONT_WASHER_Z[0] - BANK_END_FEELER
STRAP_INNER_SPAN = BACK_STRAP_INNER_Z - FRONT_STRAP_INNER_Z
# Cam / connecting-rod ring mid-plane relative to its gear's station: the cam
# spans FACE_WIDTH/2 .. FACE_WIDTH/2 + CAM_THICKNESS south of it.
CAM_MID_DZ = -(FACE_WIDTH + CAM_THICKNESS) / 2.0

# --- pedestals, arbor and set screws (nominal, bank pushed back) ------------
# Each MHA-004 stands on its strap INNER face (U34 row 5): the front one as
# built (local +z = machine +z), the back one turned 180 about y (local +z =
# machine -z). Their origins follow from those faces.
FRONT_PEDESTAL_ORIGIN_Z = FRONT_STRAP_INNER_Z - _pedestal.STRAP_INNER_Z
BACK_PEDESTAL_ORIGIN_Z = BACK_STRAP_INNER_Z + _pedestal.STRAP_INNER_Z
STRAP_OUTER_SPAN = STRAP_INNER_SPAN + 2.0 * _pedestal.STRAP_T
# The arbor fills both strap bores end to end, so the MHA-147 apex set screws
# (each at its strap's mid-depth) bear on it, and each end is domed
# ARBOR_DOME_HEIGHT proud of its strap's outer face. Its cylinder IS the span
# over both straps, the length the fitter measures and cuts to (#743,
# superseding U34b's "span less 6.0").
ARBOR_DOME_HEIGHT = 1.5
ARBOR_LENGTH = STRAP_OUTER_SPAN
ARBOR_SOUTH_Z = FRONT_STRAP_INNER_Z - _pedestal.STRAP_T
ARBOR_OVERALL_LENGTH = ARBOR_LENGTH + 2.0 * ARBOR_DOME_HEIGHT
FRONT_SET_SCREW_Z = FRONT_PEDESTAL_ORIGIN_Z + _pedestal.SET_SCREW_Z
BACK_SET_SCREW_Z = BACK_PEDESTAL_ORIGIN_Z - _pedestal.SET_SCREW_Z
# Each screw stands radially on the arbor's top with its cup rim touching;
# its socket face then sits this far over the crown apex (nominal arbor
# concentric in its bore). The drive train places it exactly there.
SET_SCREW_SOCKET_PROUD = (
    _screw.LENGTH + _shaft.SHAFT_DIA / 2.0 - _pedestal.TOP_RADIUS
)
# Tightened, the screw pushes the arbor to the bottom of its bore. With the
# largest bore and the smallest arbor the cup rim then sits lowest, and the
# plain cup point (not the first full thread) must still span the running
# clearance up to the bore wall, by this margin (the rig's 0.25 spare).
SET_SCREW_POINT_MARGIN_MIN = 0.25
_BORE_MAX_R = (_pedestal.BORE_DIA + _pedestal.BORE_DIA_BAND[0]) / 2.0
_SHAFT_MIN_R = (_shaft.SHAFT_DIA + _shaft.SHAFT_DIA_BAND[1]) / 2.0
SET_SCREW_POINT_MARGIN = (
    (2.0 * _SHAFT_MIN_R - _BORE_MAX_R) + _screw.POINT_LENGTH - _BORE_MAX_R
)
if SET_SCREW_POINT_MARGIN < SET_SCREW_POINT_MARGIN_MIN:
    raise AssertionError(
        f"apex set-screw cup point spans the bore clearance by less than the minimum "
        f"(margin {SET_SCREW_POINT_MARGIN:.3f} < {SET_SCREW_POINT_MARGIN_MIN})"
    )

# --- g0 -> g19 pitch-stack band ---------------------------------------------
# g0's tooth-front face sits at g19's back face - L20 + (T0 - FW0), i.e. g19's
# back face less gears 1-19 and gear 0's face width.
G0_FRONT_FROM_G19_BACK = G0_TOOTH_FRONT_Z - G19_BACK_FACE_Z
_G1_G19_BAND = partial_stack_band(COUNT - 1)
G0_FRONT_SOUTH_STACK = {
    "gears 1-19 overall thickness, long (L20 +/-0.20)": _G1_G19_BAND[0],
    "gear 0 face width (+0.05)": FACE_WIDTH_TOLERANCE_MM,
    "bank end play E_b max": BANK_END_PLAY[1],
}
G0_FRONT_NORTH_STACK = {
    "gears 1-19 overall thickness, short (L20 +/-0.20)": -_G1_G19_BAND[1],
    "gear 0 face width (-0.05)": FACE_WIDTH_TOLERANCE_MM,
}
# The pitch-stack band alone (without end play), south / north of nominal.
G0_G19_BAND = (
    -(_G1_G19_BAND[0] + FACE_WIDTH_TOLERANCE_MM),
    -_G1_G19_BAND[1] + FACE_WIDTH_TOLERANCE_MM,
)
# g19 is the datum: the rig sets its leaf D off g19's back face with the bank
# pushed back (north), so g19 can only move south of that, by the end play.
G19_BACK_NORTH_STACK: dict[str, float] = {}
G19_BACK_SOUTH_STACK = {"bank end play E_b max": BANK_END_PLAY[1]}
# Any gear's tooth-face mid-plane against its nominal, bank pushed back: the
# gears north of it, capped by partial_stack_band, not by the acceptance. With
# centred bands the worst station is not g0 but the one with 14 gears north.
_NORTH_OF_STATION = [partial_stack_band(COUNT - 1 - j) for j in range(COUNT)]
STATION_STACK_BAND = (
    -(max(upper for upper, _ in _NORTH_OF_STATION) + FACE_WIDTH_TOLERANCE_MM / 2.0),
    -min(lower for _, lower in _NORTH_OF_STATION) + FACE_WIDTH_TOLERANCE_MM / 2.0,
)

# --- ring support -----------------------------------------------------------
# A closed slot IS the cam: gear j's web to gear j-1's back face. Its smallest
# width is the thinnest cam (T at its bottom, FW at its top).
SLOT_MIN = OVERALL_THICKNESS + OVERALL_THICKNESS_BAND[1] - (
    FACE_WIDTH + FACE_WIDTH_TOLERANCE_MM
)
# The thinnest in-band cam still holds the thickest ring with the novice spare
# (the restated "keep T +/0": a thin gear is in band only while this holds).
RING_MAX = _rod.RING_THICKNESS + _rod.RING_THICKNESS_BAND[0]
RING_SLOT_MARGIN = SLOT_MIN - RING_MAX
if RING_SLOT_MARGIN < MARGIN_SPARE:
    raise AssertionError(
        f"the thinnest cam slot {SLOT_MIN:.4f} holds the thickest ring "
        f"{RING_MAX:.3f} by {RING_SLOT_MARGIN:.3f} < {MARGIN_SPARE}"
    )
RING_OVERHANG_MAX = BANK_END_PLAY[1]

# --- datum chain for the cone-mesh axial budget -----------------------------
BACK_STRAP_LOCATE_BAND = 0.10  # DRO edge-find on the strap inner face
DATUM_CHAIN_STACK = {
    "back strap DRO locate": BACK_STRAP_LOCATE_BAND,
    "back washer thickness": WASHER_THICK_TOLERANCE_MM,
}

__all__ = [
    "ARBOR_DOME_HEIGHT",
    "ARBOR_LENGTH",
    "ARBOR_OVERALL_LENGTH",
    "ARBOR_SOUTH_Z",
    "BACK_PEDESTAL_ORIGIN_Z",
    "BACK_SET_SCREW_Z",
    "FRONT_PEDESTAL_ORIGIN_Z",
    "FRONT_SET_SCREW_Z",
    "SET_SCREW_POINT_MARGIN",
    "SET_SCREW_POINT_MARGIN_MIN",
    "SET_SCREW_SOCKET_PROUD",
    "STRAP_OUTER_SPAN",
    "BACK_STRAP_INNER_Z",
    "BACK_WASHER_Z",
    "BANK_END_FEELER",
    "BANK_END_FEELER_BAND",
    "BANK_END_PLAY",
    "BANK_END_PLAY_TERMS",
    "BANK_PITCH",
    "CAM_MID_DZ",
    "CAM_THICKNESS",
    "COUNT",
    "DATUM_CHAIN_STACK",
    "FRONT_STRAP_INNER_Z",
    "FRONT_WASHER_Z",
    "G0_CAM_FACE_Z",
    "G0_FRONT_FROM_G19_BACK",
    "G0_FRONT_NORTH_STACK",
    "G0_FRONT_SOUTH_STACK",
    "G0_G19_BAND",
    "G0_TOOTH_FRONT_Z",
    "G19_BACK_FACE_Z",
    "G19_BACK_NORTH_STACK",
    "G19_BACK_SOUTH_STACK",
    "GEAR_THICKNESS_ACCEPT",
    "RING_MAX",
    "RING_OVERHANG_MAX",
    "RING_SLOT_MARGIN",
    "SLOT_MIN",
    "STACK_L20",
    "STACK_L20_ACCEPT",
    "STATION_STACK_BAND",
    "STATION_Z0",
    "STRAP_INNER_SPAN",
    "THERMAL_END_PLAY_DRIFT",
    "partial_stack_band",
    "station_z",
]
