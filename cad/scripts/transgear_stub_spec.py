r"""Pure-data contract for MHA-082, the transgear stud (contract §2.1, ruling R9-5).

The fixed steel stud the disc cluster runs on.  Its Ø12 collar seats on the
arm MHA-164's front face with the #10-32 rear thread screwed through the arm's
tapped hole; the feed-pinion sleeve runs on the Ø3.9 journal between the Ø9
thrust step and the journal shoulder; the MHA-160 hub cap screws onto the
#6-32 front thread and seats on that shoulder, so the cap is torqued against
the stud and never against the cluster.

Frame: one revolve about local +Z.  Local z = 0 is the collar's rear face (the
arm seat, machine z -124.4) and local +Z runs toward the machine front, so
machine z = ``ARM_SEAT_MACHINE_Z`` - local z.  Named planes: ``ArmSeat`` is
the Front Plane (z 0); ``SleeveThrust`` (z 10.75 as fitted, the Ø9 step
face); ``CapShoulder`` (z 33.65, the journal shoulder).  ``Axis1`` is the
stud axis.  The arm seat is faced to fit at assembly (R9-47), so every
make-to axial size datums on the thrust face and the model carries the
as-fitted nominal.

PURE DATA: the build and the drawing both import it; neither imports the
other.  The sleeve spec (``transgear_feed_pinion_spec``) imports the journal
names from here for the cluster-float check; nothing here imports the sleeve.
"""

from __future__ import annotations

import math

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
import transgear_arm_geometry as ARM
from transgear_arm_geometry import MM_PER_IN, STUD_TAP_CSK_DIA, STUD_TAP_SPEC

ARM_SEAT_MACHINE_Z = ARM.FRONT_FACE_MACHINE_Z

# --- Threads -----------------------------------------------------------------
# One thread authority for the cap: the MHA-160 spec taps this size.
FRONT_THREAD = "#6-32"
FRONT_THREAD_CALLOUT = f"{FRONT_THREAD} UNC"
REAR_THREAD = STUD_TAP_SPEC.size  # "#10-32", the arm's tapped hole
REAR_THREAD_CALLOUT = f"{REAR_THREAD} UNF"
# Threaded sections are plain cylinders at the basic major (fleet convention).
FRONT_THREAD_MAJOR = THREAD_MAJOR_MM[FRONT_THREAD]  # 3.505
REAR_THREAD_MAJOR = THREAD_MAJOR_MM[REAR_THREAD]  # 4.826
FRONT_THREAD_PITCH = MM_PER_IN / 32.0

# --- Faced to fit (R9-47) ------------------------------------------------------
# m is the air from F to the MHA-070 disc's front face, read on feelers with
# the knob shaft rearward, the MHA-177 drive collar slid back on the 12T and
# the disc cluster pushed forward.  F, the window's one referent, is the
# MHA-078 knob shaft's 12T front face: the drive collar's rearward stop.  The
# stud is turned long on its thrust station and the collar's rear face (the
# arm seat) is faced until m reads STUD_FIT_WINDOW; ``transgear_stud_fit``
# holds the knob chain, the fitted band and the facing it takes.
STUD_FIT_WINDOW = (0.10, 0.20)
STUD_FIT_WINDOW_TEXT = f"{STUD_FIT_WINDOW[0]:.2f}-{STUD_FIT_WINDOW[1]:.2f}"
TURN_THRUST_STATION_MIN = 11.5
TURN_THRUST_STATION = 12.2  # as turned
# The model carries the as-fitted nominal: m at the window's centre 0.15 on
# the nominal knob chain 10.90 leaves 10.75, i.e. 1.45 faced from the 12.2
# turned (``transgear_stud_fit`` asserts it).
SLEEVE_THRUST_STATION = 10.75
# Make-to sizes datum on the Ø9 step face (the sleeve's rear thrust face),
# which the facing never touches; each is a routine .X size.
STEP_LENGTH = 4.2  # the Ø12 collar's front face to the thrust face
FACE_RELIEF_FLOOR_FROM_THRUST = 8.2  # the thrust face to the face relief's floor
REAR_THREAD_END_FROM_THRUST = 20.0  # the thrust face to the rear thread's end

# --- Rear: #10-32 through the arm, domed end ----------------------------------
# The thread runs from the collar face (through the Ø5.40 face relief, which
# takes the screw-cutting run-out so full thread starts at the arm's face) to
# the dome base, REAR_THREAD_END_FROM_THRUST from the thrust face: the more
# the seat is faced, the further the dome stands behind the arm (as fitted,
# 9.25 from the seat).
REAR_THREAD_LENGTH = round(REAR_THREAD_END_FROM_THRUST - SLEEVE_THRUST_STATION, 6)
REAR_DOME_SAG = 1.0
REAR_DOME_R = ((REAR_THREAD_MAJOR / 2.0) ** 2 + REAR_DOME_SAG**2) / (
    2.0 * REAR_DOME_SAG
)
# The screw-cutting run-out at 32 tpi (R9-5): both threads run out into a
# relief at least this long.
SCREW_CUT_RUNOUT = 1.0
FACE_RELIEF_DIA = 5.40
# As fitted the floor stands 2.55 inside the seat face; the fit-up keeps its
# least depth over the run-out (``transgear_stud_fit``).
FACE_RELIEF_DEPTH = round(SLEEVE_THRUST_STATION - FACE_RELIEF_FLOOR_FROM_THRUST, 6)

# --- Collar, thrust step, journal ---------------------------------------------
COLLAR_DIA = 12.0
STEP_DIA = 9.0
# As fitted: the seat face to the collar's front face, 6.55.
COLLAR_LENGTH = round(SLEEVE_THRUST_STATION - STEP_LENGTH, 6)
# The Ø9 step face is the sleeve's rear thrust face (machine z -135.15 as
# fitted).
# The sleeve's running fit: the shared ground-shaft h band under the sleeve's
# reamed Ø3.900 +0.030/+0.012 bore.  (upper, lower) deviations.
JOURNAL_DIA = 3.900
JOURNAL_DIA_BAND = SHAFT_H
# Journal length, Ø9 step face to the shoulder, printed ±0.05 (functional:
# with the sleeve's 22.6 ±0.05 length it sets the cluster float 0.2..0.4).
JOURNAL_LENGTH = 22.9
JOURNAL_LENGTH_TOL = 0.05
# The shoulder the cap's plain rear face seats on (machine z -158.05).
CAP_SHOULDER_STATION = round(SLEEVE_THRUST_STATION + JOURNAL_LENGTH, 6)

# --- Front: #6-32 relief, thread, dome ----------------------------------------
# Thread relief in front of the shoulder (R9-5): Ø2.4 MAX under the #6-32
# root, printed as a single MAX limit (swTolMAX prints the NOMINAL then "MAX",
# so the nominal sits at the band's top).  0.3 below it keeps the neck from
# being turned needlessly thin (rule-11 pick: Ø2.1 minimum neck).
RELIEF_DIA = 2.4
RELIEF_DIA_BAND = (0.0, -0.3)  # (upper, lower)
RELIEF_DIA_TOL_TYPE = 6  # swTolType_e.swTolMAX (offline API docs, enums/swTolType_e)
# Relief width 1.1 ±0.1 (functional: the screw-cutting run-out needs 1.0 and
# the cap's engagement charges at most 1.2, R9-5's 1.0-1.2 window).
RELIEF_WIDTH = 1.1
RELIEF_WIDTH_TOL = 0.1
RELIEF_END_STATION = round(CAP_SHOULDER_STATION + RELIEF_WIDTH, 6)
# The threaded cylinder ends FRONT_THREAD_END from the shoulder; a spherical
# end of sag FRONT_DOME_SAG puts the tip at machine z -166.35 as fitted.
FRONT_THREAD_END = 6.8
FRONT_DOME_SAG = 1.5
FRONT_DOME_R = ((FRONT_THREAD_MAJOR / 2.0) ** 2 + FRONT_DOME_SAG**2) / (
    2.0 * FRONT_DOME_SAG
)
FRONT_THREAD_END_STATION = round(CAP_SHOULDER_STATION + FRONT_THREAD_END, 6)
TIP_STATION = round(FRONT_THREAD_END_STATION + FRONT_DOME_SAG, 6)
REAR_TIP_STATION = -(REAR_THREAD_LENGTH + REAR_DOME_SAG)
OVERALL_LENGTH = TIP_STATION - REAR_TIP_STATION

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "journal",
        MACHINED_UM,
        CylinderFace(
            JOURNAL_DIA,
            contains_z_mm=SLEEVE_THRUST_STATION + JOURNAL_LENGTH / 2.0,
        ),
    ),
)


def _limits(nominal: float, band: tuple[float, float]) -> tuple[float, float]:
    """``(minimum, maximum)`` of an ``(upper, lower)`` deviation band."""
    upper, lower = band
    return round(nominal + lower, 6), round(nominal + upper, 6)


# --- Decimal places ARE the tolerance (policy rule 2) --------------------------
# .XX on the face relief Ø (it clears the #10-32 major at its minimum).  The
# journal Ø prints its fit band at three places, its length its ±0.05 at two,
# the relief its MAX and ±0.1 at one.  The axial make-to sizes datum on the
# thrust face at routine .X (``transgear_stud_fit`` holds their worst cases
# over the fitted band); the thrust station prints as a REFERENCE, as fitted,
# under its turn-and-face callout.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StudProfile": {
        "RearThreadEnd",
        "FaceReliefDia",
        "FaceReliefFloor",
        "CollarDia",
        "StepLength",
        "StepDia",
        "ThrustStation",
        "JournalDia",
        "JournalLength",
        "ReliefDia",
        "ReliefWidth",
        "FrontThreadEnd",
    },
    "RearDomeProfile": {"RearDomeR"},
    "FrontDomeProfile": {"FrontDomeR"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "StudProfile": {
        "RearThreadEnd": 1,
        "FaceReliefDia": 2,
        "FaceReliefFloor": 1,
        "CollarDia": 1,
        "StepLength": 1,
        "StepDia": 1,
        "ThrustStation": 2,
        "JournalDia": 3,
        "JournalLength": 2,
        "ReliefDia": 1,
        "ReliefWidth": 1,
        "FrontThreadEnd": 1,
    },
    "RearDomeProfile": {"RearDomeR": 1},
    "FrontDomeProfile": {"FrontDomeR": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-082 dimension needs authored places")
# Faced to fit: the as-fitted station is a reference and the callout under it
# is the requirement (the MHA-172 seat washer idiom); the drawing appends the
# MHA-A06 step pointer.
REFERENCE_DIMENSIONS = frozenset({"ThrustStation"})
THRUST_STATION_CALLOUT = f"TURN {TURN_THRUST_STATION_MIN:.1f} MIN, FACED TO FIT"


def _band(name: str) -> float:
    return printed_band_mm(DRAWING_PRECISION_BY_NAME[name])


JOURNAL_DIA_MIN, JOURNAL_DIA_MAX = _limits(JOURNAL_DIA, JOURNAL_DIA_BAND)
JOURNAL_LENGTH_MIN, JOURNAL_LENGTH_MAX = _limits(
    JOURNAL_LENGTH, (JOURNAL_LENGTH_TOL, -JOURNAL_LENGTH_TOL)
)
RELIEF_DIA_MIN, RELIEF_DIA_MAX = _limits(RELIEF_DIA, RELIEF_DIA_BAND)
RELIEF_WIDTH_MIN, RELIEF_WIDTH_MAX = _limits(
    RELIEF_WIDTH, (RELIEF_WIDTH_TOL, -RELIEF_WIDTH_TOL)
)
FRONT_THREAD_END_MIN = round(FRONT_THREAD_END - _band("FrontThreadEnd"), 6)
STEP_LENGTH_MAX = round(STEP_LENGTH + _band("StepLength"), 6)
STEP_LENGTH_MIN = round(STEP_LENGTH - _band("StepLength"), 6)
FACE_RELIEF_FLOOR_MIN = round(
    FACE_RELIEF_FLOOR_FROM_THRUST - _band("FaceReliefFloor"), 6
)
FACE_RELIEF_FLOOR_MAX = round(
    FACE_RELIEF_FLOOR_FROM_THRUST + _band("FaceReliefFloor"), 6
)
REAR_THREAD_END_MIN = round(REAR_THREAD_END_FROM_THRUST - _band("RearThreadEnd"), 6)
REAR_THREAD_END_MAX = round(REAR_THREAD_END_FROM_THRUST + _band("RearThreadEnd"), 6)

# --- #10-32 in the arm (contract §7) -------------------------------------------
# R9-6 / R9-23: the arm MHA-164 is 5/16 precision-ground flat stock, faces as
# supplied, at the arm module's thickness and stock band.  The engagement
# over the fitted thrust-station band is ``transgear_stud_fit``'s.
ARM_THICKNESS_MIN = round(ARM.THICKNESS - ARM.THICKNESS_BAND, 6)
# Countersink Ø5.0 +0.10/0 on both arm faces: each takes (csk - major)/2 of
# thread.  Conservative: both faces deducted (the rear one lies under the dome
# only when the dome base clears the rear face).
ARM_CSK_LOSS_NOMINAL = (STUD_TAP_CSK_DIA - REAR_THREAD_MAJOR) / 2.0
ARM_CSK_LOSS_MAX = (STUD_TAP_CSK_DIA + drilled_oversize_mm() - REAR_THREAD_MAJOR) / 2.0
ENGAGEMENT_RULE_D = 1.5

# --- #6-32 root, relief and neck ----------------------------------------------
# ASSUMPTION (the MHA-139 construction, not sourced from ASME B1.1 here): the
# basic-profile root is major - 1.299038 P; the UNR-2A reference minimum is
# the 2A major max (0.1380 - 0.0008 in) less 1.226869 P.  The relief floor
# stays under both so the thread's last full form clears it.
FRONT_THREAD_ROOT_BASIC = (
    FRONT_THREAD_MAJOR - 1.5 * math.sqrt(3.0) / 2.0 * FRONT_THREAD_PITCH
)
FRONT_THREAD_MINOR_UNR_2A = (0.1372 - 1.226869 / 32.0) * MM_PER_IN
# The neck is the stud's weakest section at its minimum: pi/4 x 2.1^2 = 3.46
# mm^2 against the #6-32 tensile stress area 0.00909 in^2 = 5.86 mm^2 (59 %).
# The cap is set by hand with a pin spanner and the stud carries no axial
# working load, so the neck is not a limit.
NECK_AREA_MIN = math.pi / 4.0 * RELIEF_DIA_MIN**2
FRONT_TENSILE_STRESS_AREA = 0.00909 * MM_PER_IN**2

# --- Walls (contract §8) --------------------------------------------------------
# Collar over the face relief: (12.0 - 5.40)/2 = 3.30 nominal;
# (11.2 - 5.91)/2 = 2.645 at the collar .X minimum and the relief .XX maximum.
COLLAR_WALL_NOMINAL = (COLLAR_DIA - FACE_RELIEF_DIA) / 2.0
COLLAR_WALL_WORST = (
    COLLAR_DIA - _band("CollarDia") - (FACE_RELIEF_DIA + _band("FaceReliefDia"))
) / 2.0
# Face relief Ø at its minimum still clears the #10-32 major: 4.89 > 4.826.
FACE_RELIEF_DIA_MIN = round(FACE_RELIEF_DIA - _band("FaceReliefDia"), 6)
# Informational (solid stud, no bore): the Ø9 step over the #10-32 major,
# (9.0 - 4.826)/2 = 2.087 nominal, (8.2 - 4.826)/2 = 1.687 at .X.
STEP_WALL_NOMINAL = (STEP_DIA - REAR_THREAD_MAJOR) / 2.0
STEP_WALL_WORST = (STEP_DIA - _band("StepDia") - REAR_THREAD_MAJOR) / 2.0

# The model's stations, as fitted (R9-47: 0.25 forward of the contract §2
# stations; the cluster, cap and front tip move with the thrust face).
THRUST_MACHINE_Z = round(ARM_SEAT_MACHINE_Z - SLEEVE_THRUST_STATION, 6)

for _ok, _what in (
    (
        RELIEF_DIA_MAX < min(FRONT_THREAD_ROOT_BASIC, FRONT_THREAD_MINOR_UNR_2A),
        f"relief Ø{RELIEF_DIA_MAX} MAX is not under the #6-32 root "
        f"{FRONT_THREAD_ROOT_BASIC:.3f} / 2A minor {FRONT_THREAD_MINOR_UNR_2A:.3f}",
    ),
    (RELIEF_DIA == RELIEF_DIA_MAX, "swTolMAX prints the nominal: it must be the max"),
    (
        RELIEF_WIDTH_MIN >= SCREW_CUT_RUNOUT and RELIEF_WIDTH_MAX <= 1.2,
        "relief width leaves R9-5's 1.0-1.2 window",
    ),
    (
        TURN_THRUST_STATION >= TURN_THRUST_STATION_MIN,
        "the as-turned thrust station is under its TURN MIN",
    ),
    (
        math.isclose(COLLAR_LENGTH + STEP_LENGTH, SLEEVE_THRUST_STATION, abs_tol=1e-9)
        and math.isclose(
            FACE_RELIEF_DEPTH + FACE_RELIEF_FLOOR_FROM_THRUST,
            SLEEVE_THRUST_STATION,
            abs_tol=1e-9,
        ),
        "the as-fitted collar and face relief do not datum on the thrust face",
    ),
    (
        COLLAR_WALL_WORST >= 2.0,
        f"collar wall over the face relief {COLLAR_WALL_WORST:.3f} under 2.0",
    ),
    (
        FACE_RELIEF_DIA_MIN > REAR_THREAD_MAJOR,
        "face relief Ø at its minimum does not clear the #10-32 major",
    ),
    (
        FACE_RELIEF_DIA > STUD_TAP_CSK_DIA + drilled_oversize_mm(),
        "face relief inside the arm's countersink: the collar would bear on it",
    ),
    (
        FRONT_THREAD_END_STATION + FRONT_DOME_SAG == TIP_STATION,
        "front tip station",
    ),
    (
        math.isclose(ARM_SEAT_MACHINE_Z - TIP_STATION, -166.35, abs_tol=1e-6),
        "front tip is not at machine z -166.35 as fitted (R9-47)",
    ),
    (
        math.isclose(ARM_SEAT_MACHINE_Z - CAP_SHOULDER_STATION, -158.05, abs_tol=1e-6),
        "cap shoulder is not at machine z -158.05 as fitted (R9-47)",
    ),
    (
        math.isclose(THRUST_MACHINE_Z, -135.15, abs_tol=1e-6),
        "sleeve thrust step is not at machine z -135.15 as fitted (R9-47)",
    ),
    (
        math.isclose(ARM_SEAT_MACHINE_Z - REAR_TIP_STATION, -114.15, abs_tol=1e-6),
        "rear dome tip is not at machine z -114.15 as fitted (R9-47)",
    ),
    (FRONT_DOME_SAG < FRONT_DOME_R, "front end is not a spherical cap"),
    (REAR_DOME_SAG < REAR_DOME_R, "rear end is not a spherical cap"),
):
    if not _ok:
        raise AssertionError(f"MHA-082: {_what}")

DRAWING_NOTES = "TURN FROM 1/2 IN BAR. SCREW-CUT BOTH THREADS INTO THEIR RELIEFS."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"
