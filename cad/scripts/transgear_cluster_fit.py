"""The disc cluster on the MHA-PD-23 pin: its printed axial stack (R9-68, #2038).

The cluster (the MHA-PD-10 sleeve with the disc, hub and screws on it) runs on
the pin between the MHA-PD-24 rear bushing, on the arm's front face, and the
MHA-PD-25 front bushing, held by the MHA-PD-VN-61 ring on the groove's front (load)
wall.  The hub and disc are trapped axially between the sleeve's step face
(rearward: the hub's spigot seats on it and passes the disc's bore; the
hub's flange clamps the disc's front face, the spigot's length ahead of the
step) and the front bushing (forward); the D-flat carries the torque.
The hub's front face stands RECESS behind the nose, so hub and disc slide
forward off the step by that recess, independently of the sleeve, before the
hub meets the front bushing: the disc's end float is the sleeve's float plus
the recess.

Owner ruling 2026-10-28 on #2038 (option A, statistical method, no relief):
nothing in the cluster is faced to fit.  The hub, the front bushing and the
rear bushing print their lengths, and every other shop-made length in the
stack prints at the same band (``pd_cluster_stack_band``).  This module
holds the stack's lengths and its worst-case gates: the disc's end float
(``END_FLOAT_MIN``, R9-5) and the hub never proud of the nose (R9-5).  The
collar-to-disc and disc-to-platen air are statistical stacks
(``pd_cluster_air``, machining-dfm.md "air stack" method).

Every chain runs from the arm's REAR face, where the pin's head and the
MHA-PD-19 plate both seat.  F is the MHA-PD-08 knob shaft's 15T front face (the
drive collar's seat), knob rearward:

    F       = plate hub face station + thrust ring + 15T face width
    m_fwd   = F - groove station + ring + front bushing + hub - spigot
              (F to the disc front face, cluster, hub and disc forward)
    float   = groove station - ring - front bushing - hub - arm thickness
              - rear bushing - tooth length
    recess  = sleeve overall - tooth length - hub

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
import pd_vn_transgear_retaining_ring_spec as RING
from pd_cluster_stack_band import PRINTED_LENGTH_BAND_IN

# --- the three printed cluster lengths (owner ruling 2026-10-28, #2038) ---------
# Collar air 0.10 MIN statistically sets the front bushing; the end float's
# worst-case 0.20 MIN sets the rear bushing; the hub stands never proud of the
# nose at the worst case (pd_cluster_air derives the first; the gates below
# hold the other two).  #290: each is the exact millimetre value of a .001 in
# nominal and prints at four places, the band's +/-.0007.  The .125 pin's
# REAM_SLIDE running fits cock the sleeve and the front bushing more than the
# metric G7 did, so the front bushing grew .002 (raising m_fwd) and the rear
# bushing gave the same .002 back to the end float.
LENGTH_BAND = PRINTED_LENGTH_BAND_IN  # the inch hub and bushings
LENGTH_PLACES = 4
HUB_LENGTH = 13.6906  # .539
FRONT_BUSHING_LENGTH = 5.6388  # .222
REAR_BUSHING_LENGTH = 5.6388  # .222

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
LRB = ("MHA-PD-24 rear bushing length", REAR_BUSHING_LENGTH, LENGTH_BAND)

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
# The disc's end float: hub and disc from the step (sleeve on the rear
# bushing) to the front bushing (bushing on the ring).
END_FLOAT_CHAIN = (
    (GS, 1),
    (RT, -1),
    (LFB, -1),
    (LHUB, -1),
    (AT, -1),
    (LRB, -1),
    (TL, -1),
)
END_FLOAT_NOMINAL = _nominal(END_FLOAT_CHAIN)
END_FLOAT_BAND = _spread(END_FLOAT_CHAIN)
END_FLOAT_RANGE = (
    round(END_FLOAT_NOMINAL - END_FLOAT_BAND, 6),
    round(END_FLOAT_NOMINAL + END_FLOAT_BAND, 6),
)
END_FLOAT_MIN = 0.20  # R9-5: the disc runs free, at the worst case
# The hub's front face behind the sleeve's nose (hub on the step).
RECESS_CHAIN = ((OL, 1), (TL, -1), (LHUB, -1))
RECESS_NOMINAL = _nominal(RECESS_CHAIN)
RECESS_BAND = _spread(RECESS_CHAIN)
RECESS_RANGE = (
    round(RECESS_NOMINAL - RECESS_BAND, 6),
    round(RECESS_NOMINAL + RECESS_BAND, 6),
)
# The sleeve's rear face forward of the arm's front face, cluster forward:
# the rear bushing can follow it there (the pinion over the rack, the
# bushing to the rack's back face: build_pd_paper_drive_assembly).
SLEEVE_REAR_FORWARD_CHAIN = ((GS, 1), (AT, -1), (RT, -1), (LFB, -1), (OL, -1))
SLEEVE_REAR_FORWARD_FROM_ARM = (
    round(_nominal(SLEEVE_REAR_FORWARD_CHAIN) - _spread(SLEEVE_REAR_FORWARD_CHAIN), 6),
    round(_nominal(SLEEVE_REAR_FORWARD_CHAIN) + _spread(SLEEVE_REAR_FORWARD_CHAIN), 6),
)

# Machine z of the model's faces: every length nominal, the cluster REARWARD
# (the sleeve on the rear bushing, its float open between the front bushing
# and the ring, the ring on the groove's load wall; hub and disc on the
# step, the recess open).  Machine -Z is forward.
ARM_REAR_Z = PIN.HEAD_SEAT_MACHINE_Z  # -116.4625
ARM_FRONT_Z = ARM.FRONT_FACE_MACHINE_Z  # -124.4
REAR_BUSHING_REAR_Z = ARM_FRONT_Z
SLEEVE_REAR_Z = round(ARM_FRONT_Z - REAR_BUSHING_LENGTH, 6)
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
# end float.
MODEL_M = round(DISC_FRONT_Z - F_Z, 6)

# Running fits on the pin (sleeve and both bushings share the bore band).
BORE_DIA_BAND = SLEEVE.BORE_DIA_BAND
BORE_DIAMETRAL_CLEARANCE = (
    round(BORE_DIA_BAND[1] - PIN.DIA_BAND[0], 6),
    round(BORE_DIA_BAND[0] - PIN.DIA_BAND[1], 6),
)

for _ok, _what in (
    (
        END_FLOAT_RANGE[0] >= END_FLOAT_MIN - 1e-9,
        f"the disc's end float {END_FLOAT_RANGE} mm closes under {END_FLOAT_MIN} at the worst case",
    ),
    (
        RECESS_RANGE[0] >= -1e-9,
        f"the hub stands proud of the sleeve's nose at the worst case: {RECESS_RANGE}",
    ),
    (
        math.isclose(MODEL_M, M_FWD_NOMINAL + END_FLOAT_NOMINAL, abs_tol=1e-6),
        f"the model's m {MODEL_M} is not m_fwd plus the end float",
    ),
    (
        math.isclose(
            SLEEVE_FLOAT_MODEL, END_FLOAT_NOMINAL - RECESS_NOMINAL, abs_tol=1e-6
        ),
        f"the model's sleeve float {SLEEVE_FLOAT_MODEL} is not the end float less the recess",
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
        "a printed cluster length is off its .001 in grid",
    ),
):
    if not _ok:
        raise AssertionError(f"#2038 cluster stack: {_what}")
