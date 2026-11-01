"""The disc cluster on the MHA-PD-23 pin: its axial stack and shim fit-up (R9-68).

The cluster (the MHA-PD-10 sleeve with the disc, hub and screws on it) runs on
the pin between the MHA-PD-24 rear bushing, on the MHA-PD-VN-68 shims on the
arm's front face, and the MHA-PD-25 front bushing, held by the MHA-PD-VN-61
ring on the groove's front (load) wall.  The hub and disc are trapped
axially between the sleeve's step face (rearward: the hub's spigot seats on
it and passes the disc's bore; the hub's flange clamps the disc's front face,
the spigot's length ahead of the step) and the front bushing (forward); the
D-flat carries the torque.  The hub's front face stands RECESS behind the
nose, so hub and disc slide forward off the step by that recess,
independently of the sleeve, before the hub meets the front bushing: the
disc's end float is the sleeve's float plus the recess.

Owner ruling 2026-11-01 (#2124, reversing #2038 option A): the float is set at
assembly with as many shims as it takes; nothing is faced.  The fitter sets
the sleeve's float, the one gap a feeler reaches (front bushing to ring,
cluster rearward), into ``RING_FLOAT_RANGE``, one shim wide over
``END_FLOAT_MIN`` (R9-5); the disc's end float is that plus the recess, so
it never closes under the floor either.  The rear bushing is short enough
that the unshimmed float always clears the floor.  The lengths that also
set the collar-to-disc air and keep the hub off the nose print +/-.001
(``pd_cluster_stack_band``); the rear bushing prints at the title block.  The
collar-to-disc and disc-to-platen air are statistical stacks
(``pd_cluster_air``, machining-dfm.md "air stack" method).

Every chain runs from the arm's REAR face, where the pin's head and the
MHA-PD-19 plate both seat.  F is the MHA-PD-08 knob shaft's 15T front face (the
drive collar's seat), knob rearward:

    F       = plate hub face station + thrust ring + 15T face width
    m_fwd   = F - groove station + ring + front bushing + hub - spigot
              (F to the disc front face, cluster, hub and disc forward)
    ring    = groove station - arm thickness - ring - front bushing
              - sleeve overall - rear bushing - shims  (the feeler's gap)
    recess  = sleeve overall - tooth length - hub
    float   = ring + recess  (the disc's end float)

Pure data: no SolidWorks.  The hub's and the bushings' specs and the
paper-drive assembly read this module; nothing it imports reads any of them.
"""

from __future__ import annotations

import math

import pd_rack_pinion_spec as DISC
import pd_transgear_arm_geometry as ARM
import pd_transgear_arm_plate_geometry as ARM_PLATE
import pd_transgear_disc_hub_geometry as HUB_JOINT
import pd_transgear_feed_pinion_spec as SLEEVE
import pd_transgear_knob_shaft_spec as KNOB_SHAFT
import pd_transgear_knob_thrust_ring_spec as KNOB_RING
import pd_transgear_pin_spec as PIN
import pd_vn_transgear_cluster_shim_spec as SHIM
import pd_vn_transgear_retaining_ring_spec as RING
from _printed_tolerance import printed_band_mm
from pd_cluster_stack_band import FIT_LENGTH_BAND_IN

# --- the three cluster lengths -----------------------------------------------------
# The statistical collar air (0.10 MIN, pd_cluster_air) and the hub never
# proud of the nose hold the hub and the front bushing to +/-.001; the rear
# bushing only feeds the shimmed end float, so it prints .XXX at the title
# block.  Each is the exact millimetre value of a .001 in nominal.  The rear
# bushing is short by the shims' room: the unshimmed float's worst case
# still clears the floor.
LENGTH_BAND = FIT_LENGTH_BAND_IN  # the hub and the front bushing
LENGTH_PLACES = 3
REAR_BUSHING_LENGTH_BAND = printed_band_mm(LENGTH_PLACES, unit=PIN.UNIT)
HUB_LENGTH = 13.6906  # .539
FRONT_BUSHING_LENGTH = 5.6388  # .222
REAR_BUSHING_LENGTH = 5.4356  # .214

# --- the stack's terms: (label, nominal, band) ------------------------------------
PH = (
    "MHA-PD-19 hub face station",
    ARM_PLATE.HUB_FACE_TO_MOUNTING,
    ARM_PLATE.HUB_FACE_TO_MOUNTING_BAND,
)
TR = ("MHA-PD-15 thrust ring length", KNOB_RING.LENGTH, KNOB_RING.LENGTH_TOL)
FW = ("MHA-PD-08 15T face width", KNOB_SHAFT.FACE_WIDTH, KNOB_SHAFT.FACE_WIDTH_BAND)
GS = ("MHA-PD-23 groove station", PIN.GROOVE_STATION, PIN.GROOVE_STATION_BAND)
RT = ("MHA-PD-VN-61 ring thickness", RING.THICKNESS, RING.THICKNESS_TOL)
AT = ("MHA-PD-18 arm thickness", ARM.THICKNESS, ARM.THICKNESS_BAND)
OL = ("MHA-PD-10 overall length", SLEEVE.OVERALL_LENGTH, SLEEVE.OVERALL_LENGTH_BAND)
TL = ("MHA-PD-10 tooth length", SLEEVE.FACE_WIDTH, SLEEVE.FACE_WIDTH_BAND)
SP = ("MHA-PD-17 spigot length", HUB_JOINT.SPIGOT_LENGTH, HUB_JOINT.SPIGOT_LENGTH_BAND)
LHUB = ("MHA-PD-17 hub length", HUB_LENGTH, LENGTH_BAND)
LFB = ("MHA-PD-25 front bushing length", FRONT_BUSHING_LENGTH, LENGTH_BAND)
LRB = ("MHA-PD-24 rear bushing length", REAR_BUSHING_LENGTH, REAR_BUSHING_LENGTH_BAND)

Term = tuple[str, float, float]


def _nominal(chain: tuple[tuple[Term, int], ...]) -> float:
    return round(sum(sign * term[1] for term, sign in chain), 6)


def _spread(chain: tuple[tuple[Term, int], ...]) -> float:
    return round(sum(term[2] for term, _ in chain), 6)


F_CHAIN = ((PH, 1), (TR, 1), (FW, 1))
F_FROM_ARM_REAR = _nominal(F_CHAIN)  # 31.6375
F_BAND = _spread(F_CHAIN)
# F to the disc's front face, cluster, hub and disc forward (knob rearward):
# the front bushing on the ring, the hub on the bushing.
M_FWD_CHAIN = (
    *F_CHAIN,
    (GS, -1),
    (RT, 1),
    (LFB, 1),
    (LHUB, 1),
    (SP, -1),
)
M_FWD_NOMINAL = _nominal(M_FWD_CHAIN)
M_FWD_BAND = _spread(M_FWD_CHAIN)
# The sleeve's float at the ring before the shims: the sleeve on the rear
# bushing on the arm, the front bushing on the nose, to the ring.
RING_FLOAT_CHAIN = (
    (GS, 1),
    (AT, -1),
    (RT, -1),
    (LFB, -1),
    (OL, -1),
    (LRB, -1),
)
UNSHIMMED_FLOAT_NOMINAL = _nominal(RING_FLOAT_CHAIN)
UNSHIMMED_FLOAT_BAND = _spread(RING_FLOAT_CHAIN)
UNSHIMMED_FLOAT_RANGE = (
    round(UNSHIMMED_FLOAT_NOMINAL - UNSHIMMED_FLOAT_BAND, 6),
    round(UNSHIMMED_FLOAT_NOMINAL + UNSHIMMED_FLOAT_BAND, 6),
)
END_FLOAT_MIN = 0.20  # R9-5: the disc runs free, at the worst case

# --- shim fit-up (owner ruling 2026-11-01, #2124) ----------------------------------
# Shims go on under the rear bushing while the ring gap less the next shim
# still clears END_FLOAT_MIN, so the gap ends inside one shim of the floor:
# RING_FLOAT_RANGE.  The count runs from none (the shortest unshimmed gap)
# to the most the longest takes in the thinnest shims.
RING_FLOAT_RANGE = (END_FLOAT_MIN, round(END_FLOAT_MIN + SHIM.THICKNESS_MAX, 6))
SHIM_COUNT_RANGE = (
    max(
        0,
        math.ceil(
            (UNSHIMMED_FLOAT_RANGE[0] - RING_FLOAT_RANGE[1]) / SHIM.THICKNESS_MAX
        ),
    ),
    math.floor((UNSHIMMED_FLOAT_RANGE[1] - END_FLOAT_MIN) / SHIM.THICKNESS_MIN),
)
# The model carries the nominal cluster's count at catalogue nominal.
SHIM_COUNT_MODEL = 2
SHIM_STACK_MODEL = round(SHIM_COUNT_MODEL * SHIM.THICKNESS, 6)
RING_FLOAT_MODEL = round(UNSHIMMED_FLOAT_NOMINAL - SHIM_STACK_MODEL, 6)

# The hub's front face behind the sleeve's nose (hub on the step).
RECESS_CHAIN = ((OL, 1), (TL, -1), (LHUB, -1))
RECESS_NOMINAL = _nominal(RECESS_CHAIN)
RECESS_BAND = _spread(RECESS_CHAIN)
RECESS_RANGE = (
    round(RECESS_NOMINAL - RECESS_BAND, 6),
    round(RECESS_NOMINAL + RECESS_BAND, 6),
)
# The disc's end float once shimmed: the ring gap plus the recess.
END_FLOAT_RANGE = (
    round(RING_FLOAT_RANGE[0] + RECESS_RANGE[0], 6),
    round(RING_FLOAT_RANGE[1] + RECESS_RANGE[1], 6),
)
END_FLOAT_MODEL = round(RING_FLOAT_MODEL + RECESS_NOMINAL, 6)

# The sleeve's rear face forward of the arm's front face, cluster forward:
# the rear bushing can follow it there (the pinion over the rack, the
# bushing to the rack's back face: build_pd_paper_drive_assembly).
SLEEVE_REAR_FORWARD_CHAIN = ((GS, 1), (AT, -1), (RT, -1), (LFB, -1), (OL, -1))
SLEEVE_REAR_FORWARD_FROM_ARM = (
    round(_nominal(SLEEVE_REAR_FORWARD_CHAIN) - _spread(SLEEVE_REAR_FORWARD_CHAIN), 6),
    round(_nominal(SLEEVE_REAR_FORWARD_CHAIN) + _spread(SLEEVE_REAR_FORWARD_CHAIN), 6),
)
# The step, cluster rearward, once shimmed: the shims and the rear bushing
# together are the ring-gap chain's remainder, so the step sits off the
# ring's load wall by the forward chain's lengths, the tooth length and the
# shimmed gap.  Its sources replace the rear bushing in the disc-to-platen
# stack (build_pd_paper_drive_assembly).
SHIM_WINDOW_LABEL = "MHA-PD-VN-68 shim fit-up window"
SHIMMED_STEP_TERMS = (
    *((label, band) for label, _, band in (GS, AT, RT, LFB, OL, TL)),
    (SHIM_WINDOW_LABEL, round(RING_FLOAT_RANGE[1] - RING_FLOAT_RANGE[0], 6)),
)

# Machine z of the model's faces: every length nominal, the nominal shim
# count, the cluster REARWARD (the sleeve on the rear bushing, its float
# open between the front bushing and the ring, the ring on the groove's load
# wall; hub and disc on the step, the recess open).  Machine -Z is forward.
ARM_REAR_Z = PIN.HEAD_SEAT_MACHINE_Z  # -116.4625
ARM_FRONT_Z = ARM.FRONT_FACE_MACHINE_Z  # -124.4
SHIM_REAR_Z = ARM_FRONT_Z  # the first shim on the arm's front face
REAR_BUSHING_REAR_Z = round(ARM_FRONT_Z - SHIM_STACK_MODEL, 6)
SLEEVE_REAR_Z = round(REAR_BUSHING_REAR_Z - REAR_BUSHING_LENGTH, 6)
STEP_Z = round(SLEEVE_REAR_Z - SLEEVE.FACE_WIDTH, 6)  # the spigot's seat
DISC_FRONT_Z = round(SLEEVE_REAR_Z - SLEEVE.DISC_FRONT_STATION, 6)
DISC_REAR_Z = round(DISC_FRONT_Z + DISC.FACE_WIDTH, 6)
NOSE_Z = round(SLEEVE_REAR_Z - SLEEVE.OVERALL_LENGTH, 6)
HUB_FRONT_Z = round(STEP_Z - HUB_LENGTH, 6)
FRONT_BUSHING_REAR_Z = NOSE_Z
FRONT_BUSHING_FRONT_Z = round(NOSE_Z - FRONT_BUSHING_LENGTH, 6)
RING_FRONT_Z = PIN.GROOVE_LOAD_WALL_MACHINE_Z
RING_REAR_Z = round(RING_FRONT_Z + RING.THICKNESS, 6)
# The sleeve's float the model leaves open at the ring.
SLEEVE_FLOAT_MODEL = round(FRONT_BUSHING_FRONT_Z - RING_REAR_Z, 6)
F_Z = round(ARM_REAR_Z - F_FROM_ARM_REAR, 6)  # the knob train's station
# F to the model disc's front face: the cluster rearward, so m_fwd plus the
# model's end float.
MODEL_M = round(DISC_FRONT_Z - F_Z, 6)

# Running fits on the pin (sleeve and both bushings share the bore band).
BORE_DIA_BAND = SLEEVE.BORE_DIA_BAND
BORE_DIAMETRAL_CLEARANCE = (
    round(BORE_DIA_BAND[1] - PIN.DIA_BAND[0], 6),
    round(BORE_DIA_BAND[0] - PIN.DIA_BAND[1], 6),
)

for _ok, _what in (
    (
        UNSHIMMED_FLOAT_RANGE[0] >= END_FLOAT_MIN - 1e-9,
        f"the unshimmed ring gap {UNSHIMMED_FLOAT_RANGE} mm closes under "
        f"{END_FLOAT_MIN} at the worst case",
    ),
    (
        RING_FLOAT_RANGE[0] <= RING_FLOAT_MODEL < RING_FLOAT_RANGE[1],
        f"the model's {SHIM_COUNT_MODEL} shims leave {RING_FLOAT_MODEL} mm at the "
        f"ring, off the window {RING_FLOAT_RANGE}",
    ),
    (
        SHIM_COUNT_RANGE[0] <= SHIM_COUNT_MODEL <= SHIM_COUNT_RANGE[1],
        f"the model's {SHIM_COUNT_MODEL} shims are off the fit-up's {SHIM_COUNT_RANGE}",
    ),
    (
        RECESS_RANGE[0] >= -1e-9,
        f"the hub stands proud of the sleeve's nose at the worst case: {RECESS_RANGE}",
    ),
    (
        math.isclose(MODEL_M, M_FWD_NOMINAL + END_FLOAT_MODEL, abs_tol=1e-6),
        f"the model's m {MODEL_M} is not m_fwd plus the model's end float",
    ),
    (
        math.isclose(SLEEVE_FLOAT_MODEL, RING_FLOAT_MODEL, abs_tol=1e-6),
        f"the model's ring gap {SLEEVE_FLOAT_MODEL} is not the shimmed chain's "
        f"{RING_FLOAT_MODEL}",
    ),
    (
        math.isclose(HUB_FRONT_Z - NOSE_Z, RECESS_NOMINAL, abs_tol=1e-6),
        f"the model's hub front face {HUB_FRONT_Z} is not the nominal recess behind the nose {NOSE_Z}",
    ),
    (
        BORE_DIAMETRAL_CLEARANCE[0] > 0.0,
        f"the pin binds in its running bores: {BORE_DIAMETRAL_CLEARANCE}",
    ),
    (
        all(
            math.isclose(round(length / 25.4, 3) * 25.4, length, abs_tol=1e-9)
            for length in (HUB_LENGTH, FRONT_BUSHING_LENGTH, REAR_BUSHING_LENGTH)
        ),
        "a cluster length is off its .001 in grid",
    ),
):
    if not _ok:
        raise AssertionError(f"disc cluster stack: {_what}")
