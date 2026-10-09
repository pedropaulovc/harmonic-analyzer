r"""Axial (machine-z) layout of the cylinder-gear bank and its retention
(issue #743) -- one source for the drive-train assembly, the channel cam plane
and the alignment-pinion rig's worst stacks.

GEOMETRY ONLY: no drawing notes, no annotation contract, no drawing-spec
imports, and no title-block reads (the ``pinion_rig_layout`` precedent), so a
print-wording edit can never re-key the drive train.

The bank is a SOLID STACK. Each MHA-DT-012 gear's overall thickness, cam face to
back face, is the station pitch, so neighbouring gears bear cam face on back
face, as the rocker hubs do (``ch_rocker_arm_spec.HUB_LENGTH``). A turned thrust
washer (MHA-DT-026) sits at each end between the end gear and its arbor-pedestal
strap.

* The BACK (north) strap is the bank's axial datum. Its inner face is
  DRO-located at fit-up, offset by the measured back washer's deviation from
  nominal (MIC_RESIDUAL is what is left of that washer's band), and the bank
  is held back against it: g19's back face bears on the back washer, which
  bears on the back strap.
* The arbor fills both strap bores and domes proud of each strap; a set
  screw in each pedestal's crown apex bears on it (MHA-VN-034): the back one
  fixes the arbor, the front one is tightened once the front strap is set.
* The FRONT (south) strap is set off the front washer by one BANK_SPRING_SET
  blade, and the MHA-VN-050 wave spring (``vn_cylinder_bank_spring_spec``)
  squeezed in that gap preloads the whole stack north onto the datum.
* Every gear's overall thickness is +/-0.025 on its print (user ruling L20
  d'). A fit-up acceptance on the measured 20-gear stack (STACK_L20_ACCEPT,
  +/-0.10, #948 ruling R) caps the cumulative deviation, so g0's position
  relative to g19 never carries 19 per-gear bands. A part of the stack is
  not capped by the acceptance alone: its gears may all lean one way while
  the rest lean the other (partial_stack_band).

The bank is PRELOADED (#948 ruling R, PR #1292, reversing the #743 Q1 ruling
"the bank is not preloaded"): no gear interface opens in service, so the
bank has no end play and a connecting-rod ring never overhangs its cam.

Stacks are dicts of named, non-negative terms, summed like
``pinion_rig_layout.DRUM_BACK_ADVANCE_STACK``. "South" is machine -z (the
front, gear 0, crank side); "north" is +z (the back, gear 19).
"""

from __future__ import annotations

import math

import _config
import dt_arbor_pedestal_spec as _pedestal
import vn_arbor_set_screw_spec as _screw
import ch_connecting_rod_spec as _rod
import vn_cylinder_bank_spring_spec as _spring
import dt_cylinder_gear_shaft_spec as _shaft
from dt_cylinder_end_disc_spec import (
    WASHER_THICK,
    WASHER_THICK_TOLERANCE_MM,
)
from dt_cylinder_gear_spec import (
    CAM_THICKNESS,
    FACE_WIDTH,
    FACE_WIDTH_TOLERANCE_MM,
    OVERALL_THICKNESS,
    OVERALL_THICKNESS_BAND,
)

COUNT = 20  # the bank is the full set of 20 cylinder gears (every build)

# --- station pitch --------------------------------------------------------
# The drive-train ladders the gears at the cone-incline z-pitch (the same
# formula as build_dt_drive_train_assembly.Z_PITCH). The gear's printed overall
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


# --- preload (#948 ruling R) ----------------------------------------------------
# The front strap is set off the front washer by one blade of the metric gauge
# set; the MHA-VN-050 wave spring in that gap holds the stack north, so the
# bank has no end play. The blade is the spring's installed height; the strap's
# set error (re-set on its hold-downs) moves only the spring's height, and with
# it the preload, never a gear.
MARGIN_SPARE = 0.25  # novice spare over every floor (pinion_rig_layout rule)
FEELER_STEP = 0.05  # blades of the metric gauge set (pinion_rig_fitup)
BANK_SPRING_SET = _spring.INSTALLED_HEIGHT  # the set blade, 0.95
BANK_SPRING_SET_BAND = 0.10  # set error: front strap re-set on its hold-downs
BANK_SPRING_HEIGHT = (
    BANK_SPRING_SET - BANK_SPRING_SET_BAND,
    BANK_SPRING_SET + BANK_SPRING_SET_BAND,
)
# (min, max) preload, N, over the set band [INFERENCE: linear rate].
BANK_PRELOAD = (
    _spring.spring_load(BANK_SPRING_HEIGHT[1]),
    _spring.spring_load(BANK_SPRING_HEIGHT[0]),
)
# The ruling's "light force": single-digit newtons, enough to hold the stack
# north against its axial drag on the arbor (#948 analysis: ~0.3 N of turning
# drag per gear at 3 N, mu 0.15) [INFERENCE: the 1 N floor].
PRELOAD_LIMITS = (1.0, 10.0)
if abs(BANK_SPRING_SET / FEELER_STEP - round(BANK_SPRING_SET / FEELER_STEP)) > 1e-9:
    raise AssertionError(f"the spring set {BANK_SPRING_SET} is not a gauge blade")
if (
    not _spring.WORKING_HEIGHT
    <= BANK_SPRING_HEIGHT[0]
    < BANK_SPRING_HEIGHT[1]
    < _spring.FREE_HEIGHT
):
    raise AssertionError(
        f"the set band {BANK_SPRING_HEIGHT} leaves {_spring.SKU}'s working range "
        f"{_spring.WORKING_HEIGHT:.4f}..{_spring.FREE_HEIGHT:.4f}"
    )
if not PRELOAD_LIMITS[0] <= BANK_PRELOAD[0] < BANK_PRELOAD[1] < PRELOAD_LIMITS[1]:
    raise AssertionError(f"the bank preload {BANK_PRELOAD} N leaves {PRELOAD_LIMITS}")
# Differential expansion of the brass stack against the iron base over
# +/-15 K. The spring takes it up: the set gap changes by this, well inside
# the set band, and the stack stays on its datum.
THERMAL_STACK_DRIFT = (19e-6 - 11e-6) * OVERALL_THICKNESS * COUNT * 15.0

# --- stack length acceptance -------------------------------------------------
STACK_L20 = COUNT * OVERALL_THICKNESS  # g0 cam face to g19 back face
# (upper, lower): re-face a long stack; remake the thinnest gear of a short
# one, which no re-facing can lengthen (user ruling L20 d', #743).
# #948 ruling R tightens the acceptance from +/-0.20: a fit-up re-face
# acceptance, not a part band.
STACK_L20_ACCEPT_BAND = (0.10, -0.10)
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

# --- nominal stations (bank held back against the datum) ---------------------
G19_BACK_FACE_Z = station_z(COUNT - 1) + FACE_WIDTH / 2.0
BACK_WASHER_Z = (G19_BACK_FACE_Z, G19_BACK_FACE_Z + WASHER_THICK)
BACK_STRAP_INNER_Z = BACK_WASHER_Z[1]
G0_TOOTH_FRONT_Z = station_z(0) - FACE_WIDTH / 2.0
G0_CAM_FACE_Z = station_z(0) + FACE_WIDTH / 2.0 - OVERALL_THICKNESS
FRONT_WASHER_Z = (G0_CAM_FACE_Z - WASHER_THICK, G0_CAM_FACE_Z)
FRONT_STRAP_INNER_Z = FRONT_WASHER_Z[0] - BANK_SPRING_SET
# The spring's installed envelope, front strap to front washer.
BANK_SPRING_Z = (FRONT_STRAP_INNER_Z, FRONT_WASHER_Z[0])
STRAP_INNER_SPAN = BACK_STRAP_INNER_Z - FRONT_STRAP_INNER_Z
# Cam / connecting-rod ring mid-plane relative to its gear's station: the cam
# spans FACE_WIDTH/2 .. FACE_WIDTH/2 + CAM_THICKNESS south of it.
CAM_MID_DZ = -(FACE_WIDTH + CAM_THICKNESS) / 2.0

# --- pedestals, arbor and set screws (nominal, bank pushed back) ------------
# Each MHA-DT-002 stands on its strap INNER face (U34 row 5): the front one as
# built (local +z = machine +z), the back one turned 180 about y (local +z =
# machine -z). Their origins follow from those faces.
FRONT_PEDESTAL_ORIGIN_Z = FRONT_STRAP_INNER_Z - _pedestal.STRAP_INNER_Z
BACK_PEDESTAL_ORIGIN_Z = BACK_STRAP_INNER_Z + _pedestal.STRAP_INNER_Z
STRAP_OUTER_SPAN = STRAP_INNER_SPAN + 2.0 * _pedestal.STRAP_T
# The arbor fills both strap bores end to end, so the MHA-VN-034 apex set screws
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
_L20 = f"L20 +/-{STACK_L20_ACCEPT_BAND[0]:.2f}"
# The bank is preloaded onto its datum, so neither stack carries end play.
G0_FRONT_SOUTH_STACK = {
    f"gears 1-19 overall thickness, long ({_L20})": _G1_G19_BAND[0],
    "gear 0 face width (+0.05)": FACE_WIDTH_TOLERANCE_MM,
}
G0_FRONT_NORTH_STACK = {
    f"gears 1-19 overall thickness, short ({_L20})": -_G1_G19_BAND[1],
    "gear 0 face width (-0.05)": FACE_WIDTH_TOLERANCE_MM,
}
# The pitch-stack band, south / north of nominal.
G0_G19_BAND = (
    -(_G1_G19_BAND[0] + FACE_WIDTH_TOLERANCE_MM),
    -_G1_G19_BAND[1] + FACE_WIDTH_TOLERANCE_MM,
)
# Any gear's tooth-face mid-plane against its nominal, bank held back: the
# gears north of it, capped by partial_stack_band, not by the acceptance. With
# centred bands the worst station is the one with 12 gears north (the
# acceptance's reach, 0.10 / 0.025 = 4 gears, from the middle of the stack).
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
# The shank passes between the same two tooth discs, so it must clear too.
RING_MAX = _rod.RING_THICKNESS + _rod.RING_THICKNESS_BAND[0]
SHANK_MAX = _rod.SHANK_THICKNESS + _rod.SHANK_THICKNESS_BAND[0]
RING_SLOT_MARGIN = SLOT_MIN - max(RING_MAX, SHANK_MAX)
if RING_SLOT_MARGIN < MARGIN_SPARE:
    raise AssertionError(
        f"the thinnest cam slot {SLOT_MIN:.4f} holds the thickest ring/shank "
        f"{max(RING_MAX, SHANK_MAX):.3f} by {RING_SLOT_MARGIN:.3f} < {MARGIN_SPARE}"
    )

# --- datum chain for the cone-mesh and channel axial budgets ----------------
BACK_STRAP_LOCATE_BAND = 0.10  # DRO edge-find on the strap inner face
# Fit-up compensation (#948 ruling R): the fitter mics the back MHA-DT-026 and
# offsets the back strap's DRO target by (measured - nominal), so the washer's
# band leaves the chain and only the micrometer reading's residual stays.
MIC_RESIDUAL = 0.013  # half a thou: one micrometer reading
DATUM_CHAIN_STACK = {
    "back strap DRO locate": BACK_STRAP_LOCATE_BAND,
    "back washer, mic-compensated": MIC_RESIDUAL,
}
if MIC_RESIDUAL >= WASHER_THICK_TOLERANCE_MM:
    raise AssertionError("the washer's compensation must beat its own band")

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
    "BANK_PRELOAD",
    "BANK_SPRING_HEIGHT",
    "BANK_SPRING_SET",
    "BANK_SPRING_SET_BAND",
    "BANK_SPRING_Z",
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
    "MARGIN_SPARE",
    "MIC_RESIDUAL",
    "PRELOAD_LIMITS",
    "GEAR_THICKNESS_ACCEPT",
    "RING_MAX",
    "SHANK_MAX",
    "RING_SLOT_MARGIN",
    "SLOT_MIN",
    "STACK_L20",
    "STACK_L20_ACCEPT",
    "STATION_STACK_BAND",
    "STATION_Z0",
    "STRAP_INNER_SPAN",
    "THERMAL_STACK_DRIFT",
    "partial_stack_band",
    "station_z",
]
