"""MHA-082 stud fitted on the MHA-178 shim (R9-47, R9-65): the knob chain, the
fitted thrust-station band, the shim thickness it takes and the stud's worst
cases over it.

m, the air from F (the MHA-078 knob shaft's 12T front face) to the MHA-070
disc's front face with the cluster pushed forward, is set on feelers to
``transgear_stub_spec.STUD_FIT_WINDOW`` by facing the shim between the arm
and the stud's collar.  The knob chain K is that air with the thrust station
TS (the arm's front face to the stud's Ø9 step face) left out, so the fitted
station is TS = K - m and the shim is TS less the stud's own seat-to-step
size:

    K = -journal + sleeve - gear face station - disc - arm + hub face
        + thrust ring + 12T face width

each term at its owning module's printed band.  The stud's make-to sizes
datum on the thrust face (``transgear_stub_spec``), so every stud check below
holds over the whole fitted band.  The disc-rear-to-platen air and the
collar to rack air need the platen and bar stations, so
``build_paper_drive_assembly`` asserts them from these constants.

Pure data: no SolidWorks.  Only the shim's spec, of the part specs, reads
this module, and nothing this module imports reads the shim's spec.
"""

from __future__ import annotations

import math

import rack_pinion_spec as DISC
import transgear_arm_geometry as ARM
import transgear_arm_plate_geometry as ARM_PLATE
import transgear_arm_plate_spec as ARM_PLATE_SPEC
import transgear_feed_pinion_spec as SLEEVE
import transgear_knob_shaft_spec as KNOB_SHAFT
import transgear_knob_thrust_ring_spec as RING
import transgear_stub_spec as STUB
from _printed_tolerance import printed_band_mm

# (term, nominal, band, sign): K = sum(sign * nominal), spread sum(band).
KNOB_CHAIN_TERMS: tuple[tuple[str, float, float, int], ...] = (
    ("MHA-082 journal length", STUB.JOURNAL_LENGTH, STUB.JOURNAL_LENGTH_TOL, -1),
    ("MHA-129 sleeve length", SLEEVE.SLEEVE_LENGTH, SLEEVE.SLEEVE_LENGTH_TOL, 1),
    (
        "MHA-129 gear face station",
        SLEEVE.GEAR_FACE_STATION,
        SLEEVE.STATION_TOL,
        -1,
    ),
    (
        "MHA-070 disc thickness",
        DISC.FACE_WIDTH,
        DISC.FACE_WIDTH_MAX - DISC.FACE_WIDTH,
        -1,
    ),
    ("MHA-164 arm thickness", ARM.THICKNESS, ARM.THICKNESS_BAND, -1),
    (
        "MHA-171 hub face station",
        ARM_PLATE.HUB_FACE_TO_MOUNTING,
        printed_band_mm(ARM_PLATE_SPEC.HUB_STATION_PLACES),
        1,
    ),
    ("MHA-176 thrust ring length", RING.LENGTH, RING.LENGTH_TOL, 1),
    (
        "MHA-078 12T face width",
        KNOB_SHAFT.FACE_WIDTH,
        printed_band_mm(KNOB_SHAFT.FACE_WIDTH_PLACES),
        1,
    ),
)
KNOB_CHAIN_NOMINAL = round(
    sum(sign * value for _, value, _, sign in KNOB_CHAIN_TERMS), 6
)
KNOB_CHAIN_BAND = round(sum(band for _, _, band, _ in KNOB_CHAIN_TERMS), 6)
KNOB_CHAIN_MIN = round(KNOB_CHAIN_NOMINAL - KNOB_CHAIN_BAND, 6)  # 10.2846
KNOB_CHAIN_MAX = round(KNOB_CHAIN_NOMINAL + KNOB_CHAIN_BAND, 6)  # 11.5154

# --- The fitted thrust station and the shim ---------------------------------------
# TS = K - m over the chain and the window: 10.0846 .. 11.4154.
WINDOW_MIN, WINDOW_MAX = STUB.STUD_FIT_WINDOW
WINDOW_CENTRE = (WINDOW_MIN + WINDOW_MAX) / 2.0
THRUST_STATION_FITTED_MIN = round(KNOB_CHAIN_MIN - WINDOW_MAX, 6)
THRUST_STATION_FITTED_MAX = round(KNOB_CHAIN_MAX - WINDOW_MIN, 6)
# The shim fills TS less the stud's seat-to-step size (7.7 at .X):
# 10.0846 - 8.5 = 1.5846 .. 11.4154 - 6.9 = 4.5154.
SHIM_THICKNESS_FITTED_MIN = round(
    THRUST_STATION_FITTED_MIN - STUB.SLEEVE_THRUST_STATION_MAX, 6
)
SHIM_THICKNESS_FITTED_MAX = round(
    THRUST_STATION_FITTED_MAX - STUB.SLEEVE_THRUST_STATION_MIN, 6
)
# The stud's rear relief stands wholly inside the thinnest shim, with full
# thread for RELIEF_COVER before the arm's front face (R9-65): 1.2 + 0.3.
RELIEF_COVER = 0.3
SHIM_THICKNESS_FLOOR = round(STUB.REAR_RELIEF_WIDTH_MAX + RELIEF_COVER, 6)
# The model: m at the window centre on the nominal chain, the shim 3.05.
MODEL_WINDOW_AIR = round(KNOB_CHAIN_NOMINAL - STUB.FITTED_THRUST_STATION, 6)
MODEL_SHIM_THICKNESS = round(STUB.FITTED_THRUST_STATION - STUB.SLEEVE_THRUST_STATION, 6)

# --- The stud over the fitted band (make-to sizes at .X from the thrust face) -
# The rear thread out of the arm's front face: 7.7846 .. 10.7154.
REAR_THREAD_OUT_MIN = round(STUB.REAR_THREAD_END_MIN - THRUST_STATION_FITTED_MAX, 6)
REAR_THREAD_OUT_MAX = round(STUB.REAR_THREAD_END_MAX - THRUST_STATION_FITTED_MIN, 6)
# #10-32 engagement in the arm, from the front mouth's break to the nearer of
# the dome base and the rear mouth's break, each break (title-block 0.25 MAX,
# no countersink: R9-63) counted from its leg on the tap drill.  The rear
# relief and its run-out stand inside the shim (SHIM_THICKNESS_FLOOR), so
# full thread meets the arm's front face:
# min(7.7846, 7.9121 - 0.25) - 0.25 = 7.4121 = 1.536D.
REAR_ENGAGEMENT_WORST = round(
    min(REAR_THREAD_OUT_MIN, STUB.ARM_THICKNESS_MIN - ARM.STUD_TAP_MOUTH_LOSS_MAX)
    - ARM.STUD_TAP_MOUTH_LOSS_MAX,
    6,
)
REAR_ENGAGEMENT_WORST_D = REAR_ENGAGEMENT_WORST / STUB.REAR_THREAD_MAJOR
# The arm's front face to the Ø12 collar's front face (the shim and the
# collar together) as fitted: 5.0846 .. 8.0154 (6.55 in the model).
COLLAR_FRONT_STATION_FITTED_MAX = round(
    THRUST_STATION_FITTED_MAX - STUB.STEP_LENGTH_MIN, 6
)
# The sleeve's rear face bears on the Ø9 step: (8.2 - 3.93)/2 = 2.135.
THRUST_ANNULUS_MIN = round(
    (
        STUB.STEP_DIA
        - printed_band_mm(STUB.DRAWING_PRECISION_BY_NAME["StepDia"])
        - (SLEEVE.BORE_DIA + SLEEVE.BORE_DIA_BAND[0])
    )
    / 2.0,
    6,
)
# The rear dome's tip, machine z, over the fitted band: -115.6154 .. -112.6846
# (HEAD -115.91 .. -114.89).  Behind the arm it shares no z with anything at
# the stud's xy: the MHA-171 plate spans arm stations 17.67..49.42, the stud
# stands at 68.815.
REAR_DOME_TIP_MACHINE_Z = (
    round(ARM.FRONT_FACE_MACHINE_Z + REAR_THREAD_OUT_MIN + STUB.REAR_DOME_SAG, 6),
    round(ARM.FRONT_FACE_MACHINE_Z + REAR_THREAD_OUT_MAX + STUB.REAR_DOME_SAG, 6),
)
WALL_TARGET = 2.0  # U27

for _ok, _what in (
    (
        0.0 < WINDOW_MIN < WINDOW_MAX,
        "the stud fit window must leave collar-to-disc air at its minimum",
    ),
    (
        math.isclose(MODEL_WINDOW_AIR, WINDOW_CENTRE, abs_tol=1e-6),
        f"the model's thrust station {STUB.FITTED_THRUST_STATION} leaves m "
        f"{MODEL_WINDOW_AIR:.4f} on the nominal knob chain, not the window "
        f"centre {WINDOW_CENTRE:.2f}",
    ),
    (
        SHIM_THICKNESS_FITTED_MIN >= SHIM_THICKNESS_FLOOR,
        f"the thinnest fitted shim {SHIM_THICKNESS_FITTED_MIN:.4f} does not hold "
        f"the {STUB.REAR_RELIEF_WIDTH_MAX} rear relief and {RELIEF_COVER} of "
        "full thread",
    ),
    (
        SHIM_THICKNESS_FITTED_MIN <= MODEL_SHIM_THICKNESS <= SHIM_THICKNESS_FITTED_MAX,
        f"the model's shim {MODEL_SHIM_THICKNESS} is outside the fitted band",
    ),
    (
        REAR_ENGAGEMENT_WORST_D >= STUB.ENGAGEMENT_RULE_D,
        f"#10-32 engagement in the arm {REAR_ENGAGEMENT_WORST:.3f} = "
        f"{REAR_ENGAGEMENT_WORST_D:.3f}D at the longest fitted station, under 1.5D",
    ),
    (
        THRUST_ANNULUS_MIN >= WALL_TARGET,
        f"sleeve-to-step bearing annulus {THRUST_ANNULUS_MIN:.3f} under {WALL_TARGET}",
    ),
    (
        STUB.STEP_WALL_WORST >= 1.5,
        f"Ø9 step over the #10-32 major {STUB.STEP_WALL_WORST:.3f} under 1.5",
    ),
):
    if not _ok:
        raise AssertionError(f"MHA-082 faced to fit: {_what}")
