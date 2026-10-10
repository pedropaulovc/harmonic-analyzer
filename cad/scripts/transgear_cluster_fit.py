"""The disc cluster on the MHA-PD-023 pin, faced to fit (R9-68): the hub's
fitted length, the knob chain, the two bushings' fitted bands and the
model's stations.

The cluster (the MHA-PD-010 sleeve with the disc, hub and screws on it) runs on
the pin between the MHA-PD-024 rear bushing, on the arm's front face, and the
MHA-PD-025 front bushing, held by the MHA-VN-047 ring on the groove's front (load)
wall.  The hub and disc are trapped axially between the sleeve's step face
(rearward: the hub's spigot seats on it and passes the disc's bore; the
hub's flange clamps the disc's front face, the spigot's length ahead of the
step) and the front bushing (forward); the D-flat carries the torque.
The hub's front face stands up to ``HUB_NOSE_WINDOW`` behind the nose, so hub
and disc slide forward off the step by that recess, independently of the
sleeve, before the hub meets the front bushing: the disc's end float is the
sleeve's float plus the recess.  Three windows are set at assembly, in this
order:

0. With the MHA-PD-017 hub's spigot on the step and the disc on the spigot, the
   hub's front face is faced until it stands ``HUB_NOSE_WINDOW`` behind the
   sleeve's nose, so the front bushing bears on the steel nose (the hub never
   thrusts, R9-5) and traps hub and disc against the step.
1. m, the air from F (the MHA-PD-008 knob shaft's 12T front face) to the
   MHA-PD-006 disc's front face with the knob shaft rearward and the cluster,
   hub and disc pushed FORWARD, is set to ``FIT_WINDOW`` by facing the FRONT
   bushing.  Pushed forward, the cluster bears through the front bushing on
   the ring and the hub on the bushing, so neither the rear bushing nor the
   recess enters m, and m is the disc's least air to F.
2. The sleeve's float is then set to ``SLEEVE_FLOAT_WINDOW`` by facing the
   REAR bushing, which holds the disc's end float (sleeve float plus recess)
   to ``FLOAT_WINDOW`` at any recess.

The reverse order of 1 and 2 cannot hold both: m read with the cluster
rearward is m plus the float, so a front bushing faced to that reading leaves
m from 0.00 to 0.30 and the disc can touch F.  (The cq-sketch rev 5 proposal
had the bushings' roles the other way round; this order supersedes it.)

Both chains run from the arm's REAR face, where the pin's head and the
MHA-PD-019 plate both seat, so the arm's thickness drops out of m:

    front bushing = m + recess + groove station - ring thickness
                    - (sleeve length - tooth length - spigot length) - F
    rear bushing  = F - tooth length - spigot length - arm thickness - m
                    - disc end float

with F (from the arm's rear face) = plate hub face + thrust ring + 12T face.
Each term is taken at its owning module's printed band.

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
import vn_transgear_retaining_ring_spec as RING
from _printed_tolerance import printed_band_mm

# m: F to the disc's front face, cluster forward (R9-47's window, unchanged).
FIT_WINDOW = (0.10, 0.20)
FIT_WINDOW_TEXT = f"{FIT_WINDOW[0]:.2f}-{FIT_WINDOW[1]:.2f}"
# The disc's end float, hub and disc between the step and the front bushing
# with the sleeve between its bushings (R9-5's window, unchanged).
FLOAT_WINDOW = (0.2, 0.4)
FLOAT_WINDOW_TEXT = f"{FLOAT_WINDOW[0]:.1f}-{FLOAT_WINDOW[1]:.1f}"
FIT_WINDOW_CENTRE = round(sum(FIT_WINDOW) / 2.0, 6)
FLOAT_WINDOW_CENTRE = round(sum(FLOAT_WINDOW) / 2.0, 6)

# The hub's front face behind the sleeve's nose, after facing (step 0).
HUB_NOSE_WINDOW = (0.0, 0.10)
HUB_NOSE_WINDOW_TEXT = f"{HUB_NOSE_WINDOW[0]:.2f}-{HUB_NOSE_WINDOW[1]:.2f}"
HUB_NOSE_WINDOW_CENTRE = round(sum(HUB_NOSE_WINDOW) / 2.0, 6)
# The sleeve's own float, set by the rear bushing (step 2): the disc's end
# float less the hub's recess, so the disc's stays in FLOAT_WINDOW at every
# recess the hub's facing leaves.
SLEEVE_FLOAT_WINDOW = (FLOAT_WINDOW[0], round(FLOAT_WINDOW[1] - HUB_NOSE_WINDOW[1], 6))
SLEEVE_FLOAT_WINDOW_TEXT = f"{SLEEVE_FLOAT_WINDOW[0]:.1f}-{SLEEVE_FLOAT_WINDOW[1]:.1f}"
SLEEVE_FLOAT_WINDOW_CENTRE = round(sum(SLEEVE_FLOAT_WINDOW) / 2.0, 6)

# The disc's front face stands the hub spigot's length ahead of the sleeve's
# step, so the disc's thickness enters no chain: only where its rear face
# stands.

# --- F from the arm's rear face ------------------------------------------------
# (term, nominal, band): F = sum(nominal), spread sum(band).
F_TERMS: tuple[tuple[str, float, float], ...] = (
    (
        "MHA-PD-019 hub face station",
        ARM_PLATE.HUB_FACE_TO_MOUNTING,
        ARM_PLATE.HUB_FACE_TO_MOUNTING_BAND,
    ),
    ("MHA-VN-046 thrust ring length", KNOB_RING.LENGTH, KNOB_RING.LENGTH_TOL),
    (
        "MHA-PD-008 12T face width",
        KNOB_SHAFT.FACE_WIDTH,
        printed_band_mm(KNOB_SHAFT.FACE_WIDTH_PLACES),
    ),
)
F_FROM_ARM_REAR = round(sum(value for _, value, _ in F_TERMS), 6)  # 31.6375
F_BAND = round(sum(band for _, _, band in F_TERMS), 6)  # 0.31

# --- Hub: faced to the nose (step 0) -------------------------------------------
# (term, nominal, band, sign): the hub's room from the step face (its
# spigot's seat) to the nose, H = sum(sign * nominal); hub length = H - the
# nose window.
HUB_CHAIN_TERMS: tuple[tuple[str, float, float, int], ...] = (
    ("MHA-PD-010 overall length", SLEEVE.OVERALL_LENGTH, SLEEVE.STATION_TOL, 1),
    ("MHA-PD-010 tooth length", SLEEVE.FACE_WIDTH, SLEEVE.FACE_WIDTH_BAND, -1),
)
HUB_CHAIN_NOMINAL = round(
    sum(sign * value for _, value, _, sign in HUB_CHAIN_TERMS), 6
)  # 13.75
HUB_CHAIN_BAND = round(sum(band for _, _, band, _ in HUB_CHAIN_TERMS), 6)  # 0.18
HUB_LENGTH_FITTED_MIN = round(
    HUB_CHAIN_NOMINAL - HUB_CHAIN_BAND - HUB_NOSE_WINDOW[1], 6
)  # 13.47
HUB_LENGTH_FITTED_MAX = round(
    HUB_CHAIN_NOMINAL + HUB_CHAIN_BAND - HUB_NOSE_WINDOW[0], 6
)  # 13.93
# The model: the window's centre on the nominal chain.
HUB_LENGTH_MODEL = round(HUB_CHAIN_NOMINAL - HUB_NOSE_WINDOW_CENTRE, 6)  # 13.70

# --- Front bushing: m -------------------------------------------------------------
# (term, nominal, band, sign): K = sum(sign * nominal); front bushing = K + m
# + the hub's recess (m is read with hub and disc forward on the bushing).
FRONT_CHAIN_TERMS: tuple[tuple[str, float, float, int], ...] = (
    ("MHA-PD-023 groove station", PIN.GROOVE_STATION, PIN.GROOVE_STATION_BAND, 1),
    ("MHA-VN-047 ring thickness", RING.THICKNESS, RING.THICKNESS_TOL, -1),
    ("MHA-PD-010 overall length", SLEEVE.OVERALL_LENGTH, SLEEVE.STATION_TOL, -1),
    ("MHA-PD-010 tooth length", SLEEVE.FACE_WIDTH, SLEEVE.FACE_WIDTH_BAND, 1),
    (
        "MHA-PD-017 spigot length",
        HUB_JOINT.SPIGOT_LENGTH,
        HUB_JOINT.SPIGOT_LENGTH_BAND,
        1,
    ),
    ("F from the arm's rear face", F_FROM_ARM_REAR, F_BAND, -1),
)
FRONT_CHAIN_NOMINAL = round(
    sum(sign * value for _, value, _, sign in FRONT_CHAIN_TERMS), 6
)  # 4.8775
FRONT_CHAIN_BAND = round(sum(band for _, _, band, _ in FRONT_CHAIN_TERMS), 6)
FRONT_BUSHING_FITTED_MIN = round(
    FRONT_CHAIN_NOMINAL - FRONT_CHAIN_BAND + FIT_WINDOW[0] + HUB_NOSE_WINDOW[0], 6
)  # 4.1767
FRONT_BUSHING_FITTED_MAX = round(
    FRONT_CHAIN_NOMINAL + FRONT_CHAIN_BAND + FIT_WINDOW[1] + HUB_NOSE_WINDOW[1], 6
)  # 5.9783

# --- Rear bushing: the float ------------------------------------------------------
REAR_CHAIN_TERMS: tuple[tuple[str, float, float, int], ...] = (
    ("F from the arm's rear face", F_FROM_ARM_REAR, F_BAND, 1),
    ("MHA-PD-010 tooth length", SLEEVE.FACE_WIDTH, SLEEVE.FACE_WIDTH_BAND, -1),
    (
        "MHA-PD-017 spigot length",
        HUB_JOINT.SPIGOT_LENGTH,
        HUB_JOINT.SPIGOT_LENGTH_BAND,
        -1,
    ),
    ("MHA-PD-018 arm thickness", ARM.THICKNESS, ARM.THICKNESS_BAND, -1),
)
REAR_CHAIN_NOMINAL = round(
    sum(sign * value for _, value, _, sign in REAR_CHAIN_TERMS), 6
)  # 6.45
REAR_CHAIN_BAND = round(sum(band for _, _, band, _ in REAR_CHAIN_TERMS), 6)
REAR_BUSHING_FITTED_MIN = round(
    REAR_CHAIN_NOMINAL - REAR_CHAIN_BAND - FIT_WINDOW[1] - FLOAT_WINDOW[1], 6
)  # 5.33
REAR_BUSHING_FITTED_MAX = round(
    REAR_CHAIN_NOMINAL + REAR_CHAIN_BAND - FIT_WINDOW[0] - FLOAT_WINDOW[0], 6
)  # 6.67

# --- The model: every window at its centre on the nominal chains --------------
FRONT_BUSHING_MODEL = round(
    FRONT_CHAIN_NOMINAL + FIT_WINDOW_CENTRE + HUB_NOSE_WINDOW_CENTRE, 6
)  # 5.0775
REAR_BUSHING_MODEL = round(
    REAR_CHAIN_NOMINAL - FIT_WINDOW_CENTRE - FLOAT_WINDOW_CENTRE, 6
)  # 6.0

# Machine z of the model's faces, cluster REARWARD (the sleeve on the rear
# bushing, its float open between the front bushing and the ring, the ring
# on the groove's load wall; hub and disc on the step, the recess open).
# Machine -Z is forward.
ARM_REAR_Z = PIN.HEAD_SEAT_MACHINE_Z  # -116.4625
ARM_FRONT_Z = ARM.FRONT_FACE_MACHINE_Z  # -124.4
REAR_BUSHING_REAR_Z = ARM_FRONT_Z
SLEEVE_REAR_Z = round(ARM_FRONT_Z - REAR_BUSHING_MODEL, 6)  # -130.4
STEP_Z = round(SLEEVE_REAR_Z - SLEEVE.FACE_WIDTH, 6)  # -144.0, the spigot's seat
DISC_FRONT_Z = round(SLEEVE_REAR_Z - SLEEVE.DISC_FRONT_STATION, 6)  # -147.65
DISC_REAR_Z = round(DISC_FRONT_Z + DISC.FACE_WIDTH, 6)  # -144.65
NOSE_Z = round(SLEEVE_REAR_Z - SLEEVE.OVERALL_LENGTH, 6)  # -157.75
HUB_FRONT_Z = round(STEP_Z - HUB_LENGTH_MODEL, 6)  # -157.70
FRONT_BUSHING_REAR_Z = NOSE_Z
FRONT_BUSHING_FRONT_Z = round(NOSE_Z - FRONT_BUSHING_MODEL, 6)  # -162.7775
RING_REAR_Z = round(FRONT_BUSHING_FRONT_Z - SLEEVE_FLOAT_WINDOW_CENTRE, 6)  # -163.0775
RING_FRONT_Z = round(RING_REAR_Z - RING.THICKNESS, 6)  # -163.7125
F_Z = round(ARM_REAR_Z - F_FROM_ARM_REAR, 6)  # -148.1
# m with the cluster, hub and disc forward: the disc comes forward by the
# sleeve's float and the hub's recess, together the disc's end float.
MODEL_M = round(
    DISC_FRONT_Z - (SLEEVE_FLOAT_WINDOW_CENTRE + HUB_NOSE_WINDOW_CENTRE) - F_Z, 6
)  # 0.15

# The sleeve's rear face, cluster, hub and disc forward, from the arm's front
# face: the rear bushing's fitted gap plus the sleeve's float (the rear
# bushing can follow the sleeve forward), 6.25 .. 6.87 (the 12T over the
# rack, the bushing to the rack's back face: build_pd_paper_drive_assembly).
SLEEVE_REAR_FORWARD_FROM_ARM = (
    round(REAR_CHAIN_NOMINAL - REAR_CHAIN_BAND - FIT_WINDOW[1] - HUB_NOSE_WINDOW[1], 6),
    round(REAR_CHAIN_NOMINAL + REAR_CHAIN_BAND - FIT_WINDOW[0] - HUB_NOSE_WINDOW[0], 6),
)

# Running fits on the pin (sleeve and both bushings share the bore band).
BORE_DIA_BAND = SLEEVE.BORE_DIA_BAND
BORE_DIAMETRAL_CLEARANCE = (
    round(BORE_DIA_BAND[1] - PIN.DIA_BAND[0], 3),
    round(BORE_DIA_BAND[0] - PIN.DIA_BAND[1], 3),
)  # 0.012 .. 0.038

for _ok, _what in (
    (
        math.isclose(DISC_FRONT_Z, -147.65, abs_tol=1e-6),
        f"the disc's front face {DISC_FRONT_Z} left its station -147.65",
    ),
    (
        math.isclose(MODEL_M, FIT_WINDOW_CENTRE, abs_tol=1e-6),
        f"the model's m {MODEL_M} is not the window centre",
    ),
    (
        math.isclose(RING_FRONT_Z, PIN.GROOVE_LOAD_WALL_MACHINE_Z, abs_tol=1e-6),
        "the model's ring is off the groove's load wall",
    ),
    (
        math.isclose(F_Z, -148.1, abs_tol=1e-6),
        f"F {F_Z} is off the knob train's -148.1",
    ),
    (
        math.isclose(HUB_FRONT_Z - NOSE_Z, HUB_NOSE_WINDOW_CENTRE, abs_tol=1e-6),
        f"the model's hub front face {HUB_FRONT_Z} is not the nose window's "
        f"centre behind the nose {NOSE_Z}",
    ),
    (
        HUB_LENGTH_FITTED_MIN <= HUB_LENGTH_MODEL <= HUB_LENGTH_FITTED_MAX,
        "the model's hub is outside its fitted band",
    ),
    (
        FRONT_BUSHING_FITTED_MIN <= FRONT_BUSHING_MODEL <= FRONT_BUSHING_FITTED_MAX,
        "the model's front bushing is outside its fitted band",
    ),
    (
        REAR_BUSHING_FITTED_MIN <= REAR_BUSHING_MODEL <= REAR_BUSHING_FITTED_MAX,
        "the model's rear bushing is outside its fitted band",
    ),
    (
        BORE_DIAMETRAL_CLEARANCE[0] > 0.0,
        f"the pin binds in its running bores: {BORE_DIAMETRAL_CLEARANCE}",
    ),
):
    if not _ok:
        raise AssertionError(f"R9-68 cluster fit: {_what}")
