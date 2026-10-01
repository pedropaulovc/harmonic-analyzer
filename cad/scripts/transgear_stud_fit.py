"""MHA-082 stud faced to fit (R9-47): the knob chain, the fitted thrust-station
band and the stud's worst cases over it.

m, the air from F (the MHA-078 knob shaft's 12T front face) to the MHA-070
disc's front face with the cluster pushed forward, is set on feelers to
``transgear_stub_spec.STUD_FIT_WINDOW`` by facing the stud's arm seat.  The
knob chain K is that air with the stud's thrust station TS left out, so the
faced station is TS = K - m:

    K = -journal + sleeve - gear face station - disc - arm + hub face
        + thrust ring + 12T face width

each term at its owning module's printed band.  The make-to sizes datum on
the thrust face (``transgear_stub_spec``), so every stud check below holds
over the whole fitted band.  The disc-rear-to-platen air and the collar to
rack air need the platen and bar stations, so ``build_paper_drive_assembly``
asserts them from these constants.

Pure data: no SolidWorks.  Nothing a part spec imports reads this module.
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

# --- The faced thrust station ---------------------------------------------------
# TS = K - m over the chain and the window: 10.0846 .. 11.4154.
WINDOW_MIN, WINDOW_MAX = STUB.STUD_FIT_WINDOW
WINDOW_CENTRE = (WINDOW_MIN + WINDOW_MAX) / 2.0
THRUST_STATION_FITTED_MIN = round(KNOB_CHAIN_MIN - WINDOW_MAX, 6)
THRUST_STATION_FITTED_MAX = round(KNOB_CHAIN_MAX - WINDOW_MIN, 6)
# The turned minimum leaves something to face at the longest fitted station
# (0.0846) and the most to face at the shortest (1.4154); a longer blank
# only faces more.
FACING_MIN = round(STUB.TURN_THRUST_STATION_MIN - THRUST_STATION_FITTED_MAX, 6)
FACING_MAX_AT_TURN_MIN = round(
    STUB.TURN_THRUST_STATION_MIN - THRUST_STATION_FITTED_MIN, 6
)
# The model: m at the window centre on the nominal chain, 1.45 faced from the
# 12.2 turned.
MODEL_WINDOW_AIR = round(KNOB_CHAIN_NOMINAL - STUB.SLEEVE_THRUST_STATION, 6)
MODEL_FACING = round(STUB.TURN_THRUST_STATION - STUB.SLEEVE_THRUST_STATION, 6)

# --- The stud over the fitted band (make-to sizes at .X from the thrust face) -
# The rear thread out of the seat face: 7.7846 .. 10.7154.
REAR_THREAD_OUT_MIN = round(STUB.REAR_THREAD_END_MIN - THRUST_STATION_FITTED_MAX, 6)
REAR_THREAD_OUT_MAX = round(STUB.REAR_THREAD_END_MAX - THRUST_STATION_FITTED_MIN, 6)
# The face relief's depth inside the seat: 1.0846 .. 4.0154.
FACE_RELIEF_DEPTH_MIN = round(THRUST_STATION_FITTED_MIN - STUB.FACE_RELIEF_FLOOR_MAX, 6)
FACE_RELIEF_DEPTH_MAX = round(THRUST_STATION_FITTED_MAX - STUB.FACE_RELIEF_FLOOR_MIN, 6)
# Full thread starts SCREW_CUT_RUNOUT past the relief floor; whatever of the
# run-out the shallowest relief does not hold stands in the arm's tap.
REAR_RUNOUT_IN_ARM_MAX = max(0.0, STUB.SCREW_CUT_RUNOUT - FACE_RELIEF_DEPTH_MIN)
# #10-32 engagement in the arm, from the farther of the front countersink and
# the run-out's end to the nearer of the dome base and the rear countersink:
# min(7.7846, 7.9121 - 0.137) - max(0.137, 0) = 7.638 = 1.583D.
REAR_ENGAGEMENT_WORST = round(
    min(REAR_THREAD_OUT_MIN, STUB.ARM_THICKNESS_MIN - STUB.ARM_CSK_LOSS_MAX)
    - max(STUB.ARM_CSK_LOSS_MAX, REAR_RUNOUT_IN_ARM_MAX),
    6,
)
REAR_ENGAGEMENT_WORST_D = REAR_ENGAGEMENT_WORST / STUB.REAR_THREAD_MAJOR
# The Ø12 collar's full-diameter length ahead of the face relief's floor is
# the floor and step sizes alone (the facing removes both alike): 7.4 - 5.0.
COLLAR_FULL_DIA_LENGTH_MIN = round(STUB.FACE_RELIEF_FLOOR_MIN - STUB.STEP_LENGTH_MAX, 6)
# The Ø12 collar as fitted: 5.0846 .. 8.0154 (6.55 in the model).
COLLAR_LENGTH_FITTED_MAX = round(THRUST_STATION_FITTED_MAX - STUB.STEP_LENGTH_MIN, 6)
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
    round(STUB.ARM_SEAT_MACHINE_Z + REAR_THREAD_OUT_MIN + STUB.REAR_DOME_SAG, 6),
    round(STUB.ARM_SEAT_MACHINE_Z + REAR_THREAD_OUT_MAX + STUB.REAR_DOME_SAG, 6),
)
WALL_TARGET = 2.0  # U27

for _ok, _what in (
    (
        0.0 < WINDOW_MIN < WINDOW_MAX,
        "the stud fit window must leave collar-to-disc air at its minimum",
    ),
    (
        math.isclose(MODEL_WINDOW_AIR, WINDOW_CENTRE, abs_tol=1e-6),
        f"the model's thrust station {STUB.SLEEVE_THRUST_STATION} leaves m "
        f"{MODEL_WINDOW_AIR:.4f} on the nominal knob chain, not the window "
        f"centre {WINDOW_CENTRE:.2f}",
    ),
    (
        FACING_MIN > 0.0,
        f"TURN {STUB.TURN_THRUST_STATION_MIN} MIN is under the longest fitted "
        f"thrust station {THRUST_STATION_FITTED_MAX:.4f}: the fit-up cannot "
        "reach the window",
    ),
    (
        REAR_ENGAGEMENT_WORST_D >= STUB.ENGAGEMENT_RULE_D,
        f"#10-32 engagement in the arm {REAR_ENGAGEMENT_WORST:.3f} = "
        f"{REAR_ENGAGEMENT_WORST_D:.3f}D at the most-faced stud, under 1.5D",
    ),
    (
        FACE_RELIEF_DEPTH_MIN >= STUB.SCREW_CUT_RUNOUT,
        f"face relief depth {FACE_RELIEF_DEPTH_MIN:.4f} at the most-faced stud "
        f"does not hold the {STUB.SCREW_CUT_RUNOUT} run-out",
    ),
    (
        COLLAR_FULL_DIA_LENGTH_MIN >= WALL_TARGET,
        f"Ø12 collar ahead of the face relief {COLLAR_FULL_DIA_LENGTH_MIN:.3f} "
        f"under {WALL_TARGET}",
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
