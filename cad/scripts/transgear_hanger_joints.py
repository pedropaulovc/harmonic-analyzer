r"""The hanger's screwed joints, pivot spring and tilt, at the printed bands.

PURE DATA, no SolidWorks/COM imports.  The two purchased screws' catalog
modules stay free of their mates (their stock builds rebuild only when the
catalog changes); this module reads both sides of each joint and holds the
sheet text the MHA-VN-041 purchased sheet prints.  The paper-drive assembly
may import it; no part build does.

* MHA-VN-041 pivot screw (91829A205) in the MHA-PD-007 bar's blind #8-32 tap:
  the 3/16 stock thread is in the tap, but the vendor's thread neck under
  the shoulder's end face leaves full thread only below FULL_THREAD_START;
  worst = that - one pitch (first thread).  The tap's entry countersink lies
  inside the neck zone and costs nothing more (contract §7, ruling R9-7).
  Approved below 1.5 D (the named exception).
* MHA-VN-040 plate screws (5/8 stock, cut to fit) in the MHA-PD-018 arm's through
  #8-32 taps: the bevel top sits flush with the MHA-PD-019 plate's rear face and
  each tip is cut at assembly flush with the arm's front face, so the thread
  in the arm is the arm less its two tap countersinks.  Every stock screw,
  head riding its countersink on the plate-to-arm pitch mismatch, must stand
  proud of the arm far enough for the cut to take its incomplete lead.
* The MHA-PD-020 spacer pressed on the MHA-VN-041 shoulder, and the MHA-VN-049
  spring's room under the head: shoulder - spacer - spot-face floor (from
  the arm's front face).  The spring holds the arm on the spacer, so the
  hanger's tilt is the spacer's face squareness, fixed in the bar's frame.
* The MHA-VN-042 latch pin pressed to the floor of the arm's blind end-face
  hole (R9-12): the hole's reamed band keeps the press, its depth band and
  the dowel's length grade set the proud range, the shallowest hole still
  grips the pin 1.5 D, and the pin's full diameter passes the MHA-PD-014
  hook strip's far face at every corner of the latch stack (R9-23, R9-50).
  The hook sheet prints that face's X and Y only as references, so this
  margin rests on the fit-up step (its note 3): the annealed arm is set
  square on the pin with the face at its drawn station, within the formed
  band, before the pin hole is match-drilled.
"""

from __future__ import annotations

import itertools
import math

import pd_latch_hook_geometry as HOOK
import pd_latch_hook_spec as HOOK_SPEC
import pd_support_bar_spec as BAR
import pd_transgear_arm_geometry as ARM
import pd_transgear_arm_plate_geometry as PLATE
import vn_transgear_arm_plate_screw_spec as PLATE_SCREW
import vn_transgear_pivot_screw_spec as PIVOT
import vn_transgear_latch_pin_spec as LATCH_PIN
import pd_transgear_pivot_spacer_spec as SPACER
import vn_transgear_pivot_spring_spec as SPRING

ENGAGEMENT_TARGET_D = 1.5


def _floor2(value: float) -> float:
    """A MIN never rounds up: floor to two places."""
    return math.floor(value * 100.0 + 1e-9) / 100.0


# --- MHA-VN-041 pivot screw in the bar -----------------------------------------
if PIVOT.THREAD != BAR.PIVOT_TAP_THREAD:
    raise AssertionError("the pivot screw's thread is not the bar's pivot tap")
if BAR.PIVOT_TAP_FULL_THREAD_MIN < PIVOT.THREAD_LEN:
    raise AssertionError("the bar's pivot tap is shorter than the screw's thread")
# The bar tap's 45° entry countersink stays inside the neck zone; its loss
# runs to where the leg meets the tap drill (R9-63).
_PIVOT_TAP_CSK_DEPTH = (BAR.PIVOT_TAP_CSK_DIA - BAR.PIVOT_TAP_DRILL_DIA) / 2.0
if _PIVOT_TAP_CSK_DEPTH > PIVOT.FULL_THREAD_START:
    raise AssertionError(
        "the bar tap's countersink reaches the pivot screw's full thread"
    )
PIVOT_ENGAGEMENT_NOMINAL = PIVOT.THREAD_LEN - PIVOT.FULL_THREAD_START
PIVOT_ENGAGEMENT_WORST = PIVOT_ENGAGEMENT_NOMINAL - PIVOT.FIRST_THREAD_LOSS
PIVOT_ENGAGEMENT_NOMINAL_D = PIVOT_ENGAGEMENT_NOMINAL / PIVOT.THREAD_MAJOR
PIVOT_ENGAGEMENT_WORST_D = PIVOT_ENGAGEMENT_WORST / PIVOT.THREAD_MAJOR
PIVOT_ENGAGEMENT_WORST_PRINTED = _floor2(PIVOT_ENGAGEMENT_WORST_D)
# Ruling R9-7 approved the vendor neck's worst (2.203 = 0.529 D, stated
# there rounded as 0.53 D; a MIN prints floored, 0.52 D): the joint carries
# only the shoulder's seating preload, the arm load runs on the shoulder.
# Any further loss re-opens the ruling.
PIVOT_ENGAGEMENT_APPROVED_MIN_D = 0.52
_PIVOT_PRINTED = PIVOT_ENGAGEMENT_WORST_PRINTED
if not PIVOT_ENGAGEMENT_APPROVED_MIN_D <= _PIVOT_PRINTED < ENGAGEMENT_TARGET_D:
    raise AssertionError(
        f"MHA-VN-041 worst engagement {PIVOT_ENGAGEMENT_WORST_D:.3f}D left the "
        "approved shortfall"
    )
# The tip stands clear of the shallowest flat drill bottom.
PIVOT_TIP_TO_DRILL_BOTTOM = (
    BAR.PIVOT_TAP_DRILL_DEPTH + BAR.PIVOT_TAP_DRILL_DEPTH_LIMITS[0] - PIVOT.THREAD_LEN
)
if PIVOT_TIP_TO_DRILL_BOTTOM <= 0.0:
    raise AssertionError("the pivot screw bottoms in the bar's tap")
# The shoulder's end ring bears on the bar outside the tap's countersink.
if not BAR.PIVOT_TAP_CSK_DIA < PIVOT.SHOULDER_DIA + PIVOT.SHOULDER_DIA_LIMITS[0]:
    raise AssertionError("the bar tap's countersink swallows the shoulder end")

# --- MHA-PD-020 spacer pressed on the MHA-VN-041 shoulder (R9-71) -----------------
# Pressed at the bench, its front face flush with the shoulder's end on a
# flat, so the screw seats both on the bar as one body: the spacer turns with
# the screw while it is tightened and is then fixed in the bar's frame, its
# faces' squareness with it (the fit-up reads the result).  The spacer's
# spec holds the press at both limits (SPACER.PRESS_INTERFERENCE).
_SHOULDER_MIN = PIVOT.SHOULDER_DIA + min(PIVOT.SHOULDER_DIA_LIMITS)
_SHOULDER_MAX = PIVOT.SHOULDER_DIA + max(PIVOT.SHOULDER_DIA_LIMITS)

# --- MHA-VN-049 spring room: shoulder - spacer - spot-face floor ----------------
# The spring holds the arm's front face on the spacer's rear face, so the
# hanger has no end play; the room between the spot-face floor and the head
# must stay between the spring's catalogue working height and its free
# height at every printed corner.
SPRING_ROOM_NOMINAL = (
    PIVOT.SHOULDER_LEN - SPACER.LENGTH - ARM.SPOT_FACE_FLOOR_FROM_FRONT
)
SPRING_ROOM_MIN = (
    PIVOT.SHOULDER_LEN
    + PIVOT.SHOULDER_LEN_LIMITS[0]
    - (SPACER.LENGTH + SPACER.LENGTH_BAND)
    - (ARM.SPOT_FACE_FLOOR_FROM_FRONT + ARM.SPOT_FACE_FLOOR_BAND)
)  # 0.70
SPRING_ROOM_MAX = (
    PIVOT.SHOULDER_LEN
    + PIVOT.SHOULDER_LEN_LIMITS[1]
    - (SPACER.LENGTH - SPACER.LENGTH_BAND)
    - (ARM.SPOT_FACE_FLOOR_FROM_FRONT - ARM.SPOT_FACE_FLOOR_BAND)
)  # 0.9508
if not SPRING.WORKING_HEIGHT <= SPRING_ROOM_MIN < SPRING_ROOM_MAX < SPRING.FREE_HEIGHT:
    raise AssertionError(
        f"MHA-VN-049 room {SPRING_ROOM_MIN:.4f}..{SPRING_ROOM_MAX:.4f} leaves the "
        f"spring's {SPRING.WORKING_HEIGHT:.4f}..{SPRING.FREE_HEIGHT:.4f}"
    )
if abs(SPRING.MODEL_HEIGHT - SPRING_ROOM_NOMINAL) > 1e-9:
    raise AssertionError("the spring is not modelled at the nominal room")
# [INFERENCE: the catalogue's working point read as a linear rate.]
SPRING_PRELOAD_N = (
    SPRING.RATE_N_PER_MM * (SPRING.FREE_HEIGHT - SPRING_ROOM_MAX),
    SPRING.RATE_N_PER_MM * (SPRING.FREE_HEIGHT - SPRING_ROOM_MIN),
)  # 19.2 .. 38.9

# --- Hanger tilt: fixed in the bar's frame by the spacer ---------------------
# Preloaded on the spacer's rear face, the arm stands square to the screw
# axis within the spacer's two face perpendicularities over the smallest
# face it seats on; the shoulder's float in the arm bore no longer tilts it.
# The term does not change in service: the spacer is pressed on the screw.
HANGER_TILT = (
    SPACER.REAR_FACE_PERPENDICULARITY + SPACER.FRONT_FACE_PERPENDICULARITY
) / SPACER.FACE_PERPENDICULARITY_ZONE_DIA  # rad
_FREE_PIVOT_TILT = 0.042144  # rad, the unpreloaded arm on its bore clearance
if not 0.0 < HANGER_TILT < _FREE_PIVOT_TILT / 10.0:
    raise AssertionError(f"the hanger tilt {HANGER_TILT:.6f} rad lost the spacer")

# --- Gravity against the preload's friction and tilt hold --------------------
# The hanger must still swing down onto the latch hook on its own weight,
# and the preload must hold the arm square on the spacer against the
# hanger's weight standing forward of it.  [INFERENCE: masses from the
# parts' analytic volumes (steel 7870, brass 8500 kg/m3) and levers from
# the assembly's stations; mu 0.3 dry steel and brass.]
HANGER_MASS_KG = 0.530  # [INFERENCE]
HANGER_GRAVITY_TORQUE_NMM = 187.65  # [INFERENCE] about P, at the hook
HANGER_TILT_MOMENT_NMM = 36.4  # [INFERENCE] CG forward of the spacer face
PIVOT_FRICTION_MU = 0.3  # [INFERENCE]
# The arm turns on the spacer's rear face (mean radius of the annulus from
# the arm bore to the smallest O.D.) and on the spring under the head (mean
# of its I.D. and the head).
_R_IN = ARM.PIVOT_BORE_DIA / 2.0
_R_OUT = SPACER.FACE_PERPENDICULARITY_ZONE_DIA / 2.0
_SPACER_FACE_R = 2.0 / 3.0 * (_R_OUT**3 - _R_IN**3) / (_R_OUT**2 - _R_IN**2)
_SPRING_HEAD_R = (SPRING.ID + PIVOT.HEAD_DIA) / 4.0
PIVOT_FRICTION_TORQUE_MAX_NMM = (
    PIVOT_FRICTION_MU * SPRING_PRELOAD_N[1] * (_SPACER_FACE_R + _SPRING_HEAD_R)
)  # 78
HANGER_SWING_MARGIN = HANGER_GRAVITY_TORQUE_NMM / PIVOT_FRICTION_TORQUE_MAX_NMM
if HANGER_SWING_MARGIN < 2.0:
    raise AssertionError(
        f"the pivot's friction {PIVOT_FRICTION_TORQUE_MAX_NMM:.1f} N.mm can hold "
        f"the hanger off the hook ({HANGER_GRAVITY_TORQUE_NMM:.1f} N.mm)"
    )
HANGER_TILT_HOLD_NMM = SPRING_PRELOAD_N[0] * _R_OUT  # 81
HANGER_TILT_HOLD_MARGIN = HANGER_TILT_HOLD_NMM / HANGER_TILT_MOMENT_NMM
if HANGER_TILT_HOLD_MARGIN < 2.0:
    raise AssertionError(
        f"the weakest preload holds {HANGER_TILT_HOLD_NMM:.1f} N.mm against the "
        f"hanger's {HANGER_TILT_MOMENT_NMM:.1f} N.mm tilt moment"
    )

# Head and spring in the spot face; the shoulder in the arm bore at the
# smallest bore the .XXX row accepts on the largest shoulder; the spring's
# I.D. on the shoulder, floating to the spot face's wall.
HEAD_RADIAL_CLEARANCE = (ARM.SPOT_FACE_DIA - PIVOT.HEAD_DIA) / 2.0
SHOULDER_RADIAL_CLEARANCE = (
    ARM.PIVOT_BORE_DIA - ARM.PIVOT_BORE_DIA_BAND - _SHOULDER_MAX
) / 2.0
SPRING_RIM_CLEARANCE = (
    ARM.SPOT_FACE_DIA - SPRING.OD - (SPRING.ID - _SHOULDER_MIN)
) / 2.0  # 0.21
if min(HEAD_RADIAL_CLEARANCE, SHOULDER_RADIAL_CLEARANCE, SPRING_RIM_CLEARANCE) <= 0.0:
    raise AssertionError("the pivot screw or its spring binds in the arm")

# --- MHA-VN-040 plate screws in the arm ------------------------------------------
if PLATE_SCREW.THREAD != ARM.PLATE_TAP_SPEC.size:
    raise AssertionError("the plate screws' thread is not the arm's plate tap")
if abs(PLATE_SCREW.HEAD_DIA - PLATE.CSK_DIA) > 1e-9:
    raise AssertionError("the plate's countersink is not the oval head's Ø")
if PLATE_SCREW.HEAD_ANGLE_DEG != PLATE.CSK_ANGLE_DEG:
    raise AssertionError("the plate's countersink angle is not the head's")
# Both screws enter their taps only if the plate's hole pitch and the arm's
# tap pitch disagree by no more than the shanks' float in the two holes.  Each
# part's pitch moves by both its holes' printed position bands (the arm's
# tap stations and the plate's hole stations, ±HOLE_POSITION_BAND each, the
# bands both builds apply); the smallest drilled hole floats on the largest
# (basic) #8-32 major.
PLATE_SCREW_PITCH_MISMATCH_MAX = 2.0 * ARM.HOLE_POSITION_BAND + 2.0 * (
    PLATE.HOLE_POSITION_BAND
)
# Two holes, each letting its shank stand (hole - shank) / 2 off centre.
PLATE_SCREW_PITCH_FLOAT = PLATE.SCREW_HOLE_DIA - PLATE_SCREW.THREAD_MAJOR
PLATE_SCREW_PITCH_MARGIN = PLATE_SCREW_PITCH_FLOAT - PLATE_SCREW_PITCH_MISMATCH_MAX
if PLATE_SCREW_PITCH_MARGIN <= 0.0:
    raise AssertionError(
        "MHA-VN-040 screws cannot enter both arm taps: plate-to-arm pitch mismatch "
        f"{PLATE_SCREW_PITCH_MISMATCH_MAX:.3f} > shank float "
        f"{PLATE_SCREW_PITCH_FLOAT:.3f}"
    )
# The heads, snugged together and then tightened in turn (the MHA-PD-000 step),
# seat off their countersinks' axes by half that mismatch, opposite ways.  An
# 82° head seated e off its countersink's axis rides up the cone by
# e / tan(41°) before it bears, and the screw stops that much short in the arm.
PLATE_SCREW_SEAT_ECCENTRICITY = PLATE_SCREW_PITCH_MISMATCH_MAX / 2.0
if PLATE_SCREW_SEAT_ECCENTRICITY > PLATE_SCREW_PITCH_FLOAT / 2.0:
    raise AssertionError("an MHA-VN-040 shank bears in its hole before its head seats")
PLATE_SCREW_ECCENTRIC_LIFT = PLATE_SCREW_SEAT_ECCENTRICITY / math.tan(
    math.radians(PLATE.CSK_ANGLE_DEG / 2.0)
)
# Each countersink takes thread to where its 45-degree leg meets the tap
# drill, not the major (R9-63): 0.423 at Ø4.3 over the Ø3.454 drill.
_PLATE_TAP_CSK_LOSS = ARM.PLATE_TAP_MOUTH_LOSS_MAX
# A countersink cut large or small by its printed band seats the oval head
# sunk or proud of the plate's rear face by this much.
PLATE_SCREW_SEAT_SHIFT = (
    PLATE.CSK_DIA_BAND / 2.0 / math.tan(math.radians(PLATE.CSK_ANGLE_DEG / 2.0))
)
# R9-44: with ASME B18.6.3's +0/-0.03 in length band no stock length both
# holds 1.5 D in the arm and keeps its tip out of the guide-lock sweep, so
# the 5/8 screws are cut at assembly, flush to PLATE_SCREW_CUT_PROUD_MAX
# proud of the arm's front face, the cut edge broken (MHA-DT-032's filed tip).
PLATE_SCREW_CUT_PROUD_MAX = 0.2
# Before the cut, the shortest stock screw in the thickest plate and arm, its
# head proud on a small countersink and riding its eccentric seat, still
# stands proud of the arm by its first thread past the highest cut, so every
# cut takes the incomplete lead and leaves full thread to the face.
PLATE_SCREW_STOCK_PROUD_MIN = (
    PLATE_SCREW.STOCK_LENGTH
    - PLATE_SCREW.STOCK_LENGTH_BAND[1]
    - (PLATE.THICKNESS_OVER_ARM + PLATE.BAND_XX)
    - PLATE_SCREW_SEAT_SHIFT
    - PLATE_SCREW_ECCENTRIC_LIFT
    - (ARM.THICKNESS + ARM.THICKNESS_BAND)
)
if (
    PLATE_SCREW_STOCK_PROUD_MIN
    < PLATE_SCREW_CUT_PROUD_MAX + PLATE_SCREW.FIRST_THREAD_LOSS
):
    raise AssertionError(
        f"MHA-VN-040 stock screw stands {PLATE_SCREW_STOCK_PROUD_MIN:.3f} proud of "
        "the arm: too short to cut its lead off"
    )
PLATE_SCREW_ENGAGEMENT_NOMINAL = min(
    PLATE_SCREW.LENGTH - PLATE.THICKNESS_OVER_ARM, ARM.THICKNESS
)
# Thinnest arm stock, cut flush: full thread from the rear tap countersink to
# the front face, where the front countersink and the cut-end break overlap.
PLATE_SCREW_ENGAGEMENT_WORST = (
    ARM.THICKNESS
    - ARM.THICKNESS_BAND
    - _PLATE_TAP_CSK_LOSS
    - max(_PLATE_TAP_CSK_LOSS, PLATE_SCREW.CUT_END_BREAK_MAX)
)
PLATE_SCREW_ENGAGEMENT_NOMINAL_D = (
    PLATE_SCREW_ENGAGEMENT_NOMINAL / PLATE_SCREW.THREAD_MAJOR
)
PLATE_SCREW_ENGAGEMENT_WORST_D = PLATE_SCREW_ENGAGEMENT_WORST / PLATE_SCREW.THREAD_MAJOR
if PLATE_SCREW_ENGAGEMENT_WORST_D < ENGAGEMENT_TARGET_D:
    raise AssertionError(
        f"MHA-VN-040 worst engagement {PLATE_SCREW_ENGAGEMENT_WORST_D:.3f}D < 1.5D"
    )
# The modelled (cut) tip ends short of (positive) or proud of (negative) the
# arm's front face: flush.
PLATE_SCREW_TIP_INSIDE_NOMINAL = ARM.THICKNESS - (
    PLATE_SCREW.LENGTH - PLATE.THICKNESS_OVER_ARM
)
if abs(PLATE_SCREW_TIP_INSIDE_NOMINAL) > 1e-9:
    raise AssertionError(
        "MHA-VN-040's modelled cut is not flush with the arm's front face"
    )
# Furthest a cut tip stands proud of the arm's front face: the assembly holds
# the lock-station sweep clear of this.
PLATE_SCREW_TIP_PROUD_MAX = PLATE_SCREW_CUT_PROUD_MAX

# The plate's notch face clears the arm's lower edge (the screws locate the
# plate).  Closing it, in plate-frame y: the face's .X corner heights, the
# holes' Y station, and the screws' float in the largest drilled holes on the
# thinnest 2A major -- each hole shifting c either way, a rigid plate moves a
# notch corner by up to (|1 - t| + |t|) c, t the corner's x along the screw
# pitch.  Across the edge (the face is parallel to it) the arm's .X outline
# then stands out toward the face.
_NOTCH_FLOAT = (
    PLATE.SCREW_HOLE_DIA + PLATE.DRILL_GROWTH - PLATE_SCREW.THREAD_MAJOR_MIN
) / 2.0
_HOLE_X = sorted(x for x, _y in PLATE.SCREW_HOLES)
_NOTCH_LEVER = max(
    abs(1.0 - t) + abs(t)
    for t in (
        (corner[0] - _HOLE_X[0]) / (_HOLE_X[1] - _HOLE_X[0])
        for corner in (PLATE.NOTCH_LEFT, PLATE.NOTCH_RIGHT)
    )
)
NOTCH_AIR_WORST = (
    PLATE.NOTCH_RELIEF
    - PLATE.NOTCH_BAND
    - PLATE.HOLE_POSITION_BAND
    - _NOTCH_LEVER * _NOTCH_FLOAT
) * math.cos(ARM.EDGE_LEAN) - ARM.BAND_X
if NOTCH_AIR_WORST <= 0.0:
    raise AssertionError(
        f"MHA-PD-019 notch face meets the arm's lower edge: worst air "
        f"{NOTCH_AIR_WORST:.3f}"
    )

# --- MHA-VN-042 latch pin pressed to the floor of the arm's end-face hole ---------
if abs(LATCH_PIN.DIA - ARM.PIN_HOLE_DIA) > 1e-9:
    raise AssertionError("the arm's press hole is not the latch pin's Ø")
# The reamed band against the dowel's catalogue band: interference at both
# limits, (smallest pin - largest hole, largest pin - smallest hole).
_PIN_OD_MIN = LATCH_PIN.DIA + min(LATCH_PIN.DIA_BAND)
_PIN_OD_MAX = LATCH_PIN.DIA + max(LATCH_PIN.DIA_BAND)
_PIN_HOLE_MIN = ARM.PIN_HOLE_DIA + min(ARM.PIN_HOLE_DIA_BAND)
_PIN_HOLE_MAX = ARM.PIN_HOLE_DIA + max(ARM.PIN_HOLE_DIA_BAND)
LATCH_PIN_PRESS_INTERFERENCE = (
    _PIN_OD_MIN - _PIN_HOLE_MAX,
    _PIN_OD_MAX - _PIN_HOLE_MIN,
)  # 0.0025 / 0.0176
if min(LATCH_PIN_PRESS_INTERFERENCE) <= 0.0:
    raise AssertionError("the arm's pin-hole band loses the latch pin's press")
if abs(LATCH_PIN.proud_length(ARM.PIN_HOLE_DEPTH) - LATCH_PIN.PROUD) > 1e-9:
    raise AssertionError("the arm's hole depth does not leave the latch pin PROUD")
# The depth's .XX band and the dowel's length grade move the pressed pin's
# tip by as much: 22.225 -/+ 0.254 - (8.50 +/- 0.51) = 12.961 .. 14.489.
LATCH_PIN_PROUD_RANGE = (
    LATCH_PIN.proud_length(
        ARM.PIN_HOLE_DEPTH + ARM.PIN_HOLE_DEPTH_BAND, -LATCH_PIN.LENGTH_GRADE
    ),
    LATCH_PIN.proud_length(
        ARM.PIN_HOLE_DEPTH - ARM.PIN_HOLE_DEPTH_BAND, LATCH_PIN.LENGTH_GRADE
    ),
)
# The shallowest hole: (8.50 - 0.51) - 0.443 = 7.55 of full diameter, 2.38 D.
LATCH_PIN_ENGAGEMENT_WORST_D = LATCH_PIN.press_engagement_d(
    ARM.PIN_HOLE_DEPTH - ARM.PIN_HOLE_DEPTH_BAND
)
if LATCH_PIN_ENGAGEMENT_WORST_D < LATCH_PIN.PRESS_ENGAGEMENT_MIN_D:
    raise AssertionError(
        f"the shallowest arm hole grips the latch pin"
        f" {LATCH_PIN_ENGAGEMENT_WORST_D:.2f} D, under"
        f" {LATCH_PIN.PRESS_ENGAGEMENT_MIN_D} D"
    )

# --- MHA-VN-042 pin through the MHA-PD-014 strip's far face (R9-23, R9-50) ----------
# The hook's pin hole is match-drilled from the pin at fit-up, which takes up
# where the strip lies across the pin; nothing takes up the pin's reach along
# its own axis, so its crowned end's full-diameter circle must pass the
# strip's far (+U) face, square to the pin, at every corner of the latch
# stack: the arm's tip station (.XX) and pin position (.XXX), the proud range
# above, the dowel's diameter band, the arm's angular play about the pivot
# (IntegratorE's coupled stack), the pivot tap's position and the shoulder's
# float in the arm bore, the hook's two screw holes (the bar's taps, the
# hook's printed hole positions and the screw heads' float), the sheet's
# thickness band, the formed arm's band and the ear's 90 deg bend at the
# hook sheet's angular row.  The face's printed X and Y are references; the
# fit-up (the hook sheet's note 3) sets it at its drawn station within the
# formed band, and that step is what this margin rests on.
LATCH_ARM_ANGLE_PLAY = 0.00305  # rad
# The screw holes are located from the formed ear's outer face at the base,
# so a bend off 90 deg leans the ear and the arm it carries about the base:
# the strip's far face at the pin moves by the pin axis's height above the
# base's underside times tan(bend error), and its normal tilts out of the
# machine XY plane by the bend error.  The bend centre sits 2.0..2.3 above
# the underside, so the underside is the longer, conservative lever.
EAR_BEND_LEVER = HOOK.PIN_HOLE_Z - HOOK.BAR_BACK_FACE_Z  # 9.469
_LATCH_PIVOT = HOOK.PIVOT_XY
_LATCH_THETA = math.radians(HOOK.ARM_ANGLE_DEG)  # -32.56 deg
# Each screw's centre in its hole off the model, any direction: the bar's tap
# and the hook's printed hole position (each a per-axis band, so their
# diagonal), and the head's float in the drilled #4 clearance hole.
HOOK_SCREW_SHIFT = (BAR.HOLE_POSITION_BAND + HOOK_SPEC.POSITION_TOL) * math.sqrt(
    2.0
) + HOOK_SPEC.HEAD_FLOAT_MAX
_BORE_FLOAT = (
    ARM.PIVOT_BORE_DIA
    + ARM.PIVOT_BORE_DIA_BAND
    - PIVOT.SHOULDER_DIA
    - min(PIVOT.SHOULDER_DIA_LIMITS)
) / 2.0


def hook_screw_drift(
    point: tuple[float, float],
    direction: tuple[float, float],
    shift: float = HOOK_SCREW_SHIFT,
    samples: int = 4001,
) -> float:
    """Largest move along unit ``direction`` (machine xy) of the hook's
    ``point`` when each screw's centre stands up to ``shift`` off its model
    (any direction) and the latched pin holds the pin hole across the strip
    (along N): the hook's refit puts the hole's lower edge on the pin.  The
    hook is rigid in its plane, a translation plus a turn about the screws'
    midpoint, so the screws' float turns the hook about the pin as well as
    sliding it; the turn more than doubles a pure translation's reach along
    U at the hole."""
    mid = (sum(HOOK.SCREW_X) / 2.0, HOOK.SCREW_Y)

    def turned(at: tuple[float, float]) -> tuple[float, float]:
        # d(at)/d(turn) for a turn about the midpoint: z x (at - mid).
        return (-(at[1] - mid[1]), at[0] - mid[0])

    def dot(a: tuple[float, float], b: tuple[float, float]) -> float:
        return a[0] * b[0] + a[1] * b[1]

    hole = turned(HOOK.PIN_HOLE_XY)
    target = turned(point)
    screws = [turned((x, HOOK.SCREW_Y)) for x in HOOK.SCREW_X]
    turn_max = 2.0 * shift / (HOOK.SCREW_X[1] - HOOK.SCREW_X[0])
    du, dn = dot(HOOK.ARM_U, direction), dot(HOOK.ARM_N, direction)
    worst = 0.0
    for k in range(samples):
        turn = turn_max * (2.0 * k / (samples - 1) - 1.0)
        # The pin holds the hole along N: the translation's N part cancels
        # the turn's.  Its U part ``a`` keeps each screw inside its float.
        across = -turn * dot(hole, HOOK.ARM_N)
        low, high = -math.inf, math.inf
        for screw in screws:
            off_n = across + turn * dot(screw, HOOK.ARM_N)
            if abs(off_n) > shift:
                low, high = math.inf, -math.inf
                break
            room = math.sqrt(shift**2 - off_n**2)
            off_u = turn * dot(screw, HOOK.ARM_U)
            low, high = max(low, -off_u - room), min(high, -off_u + room)
        if low > high:
            continue
        rest = across * dn + turn * dot(target, direction)
        worst = max(worst, *(abs(a * du + rest) for a in (low, high)))
    return worst


HOOK_DRIFT_ALONG_U = hook_screw_drift(HOOK.PIN_HOLE_XY, HOOK.ARM_U)


def latch_pin_far_face_margin(
    tip_band: float = ARM.TIP_STATION_BAND,
    proud_range: tuple[float, float] = LATCH_PIN_PROUD_RANGE,
    bend_deg: float = HOOK_SPEC.BEND_TOL_DEG,
) -> float:
    """Least distance, along the pin, by which the crowned end's full
    diameter passes the strip's far face over every corner of the stack."""
    signs = (-1.0, 1.0)
    radii = [(LATCH_PIN.DIA + band) / 2.0 for band in LATCH_PIN.DIA_BAND]
    sheet = (-HOOK.SHEET_T_MINUS, HOOK.SHEET_T_PLUS)
    bends = [math.radians(s * bend_deg) for s in signs]
    u0x, u0y = HOOK.ARM_U
    face0 = HOOK.on_arm(HOOK.FAR_FACE_STATION)
    worst = math.inf
    for tip, proud, r, hook, dt, tap, float_, side, play, bend in itertools.product(
        signs, proud_range, radii, signs, sheet, signs, signs, signs, signs, bends
    ):
        theta = _LATCH_THETA + play * LATCH_ARM_ANGLE_PLAY
        ux, uy = math.cos(theta), math.sin(theta)
        # The pivot tap (a per-axis band) and the shoulder's float in the
        # bore, both along the far face's normal.
        pivot_shift = tap * BAR.HOLE_POSITION_BAND * (abs(u0x) + abs(u0y))
        pivot_shift += float_ * _BORE_FLOAT
        px = _LATCH_PIVOT[0] + pivot_shift * u0x
        py = _LATCH_PIVOT[1] + pivot_shift * u0y
        full = ARM.TIP_STATION + tip * tip_band + proud - LATCH_PIN.CROWN_R
        lateral = side * ARM.HOLE_POSITION_BAND
        centre = (px + full * ux - uy * lateral, py + full * uy + ux * lateral, 0.0)
        # The far face: screwed, formed and sheet bands along U, then the
        # ear's lean about the base (along machine X at the pin's height).
        move = hook * (HOOK_DRIFT_ALONG_U + HOOK_SPEC.FORMED_BAND) + dt
        face = (
            face0[0] + move * u0x + EAR_BEND_LEVER * math.tan(bend),
            face0[1] + move * u0y,
            0.0,
        )
        normal = (u0x * math.cos(bend), u0y, -u0x * math.sin(bend))
        axis = (ux, uy, 0.0)
        along = sum(n * a for n, a in zip(normal, axis, strict=True))
        # The end circle lies square to the pin; its nearest point to the
        # face is r times the normal's part across the pin back.
        across = math.sqrt(max(0.0, 1.0 - along**2))
        gap = sum((c - f) * n for c, f, n in zip(centre, face, normal, strict=True))
        worst = min(worst, (gap - r * across) / along)
    return worst


LATCH_PIN_FAR_FACE_MARGIN_WORST = latch_pin_far_face_margin()
if LATCH_PIN_FAR_FACE_MARGIN_WORST <= 0.0:
    raise AssertionError(
        "MHA-VN-042 pin / MHA-PD-014 strip far face: the pin's full diameter stops"
        f" {-LATCH_PIN_FAR_FACE_MARGIN_WORST:.3f} short at the printed worst case"
    )


# --- The feed mesh on the latch (Codex P1 on b2eb9a0e1) -----------------------
def latch_pinion_drop(slack_along: float) -> float:
    """How far the feed pinion's centre falls, opening its mesh in the rack,
    when the free arm swings down till its latch pin has moved ``slack_along``
    across the hook strip.  The strip lies square to the pin (its face normal
    U), so the pin's travel across it is along N at HOLE_STATION from P: the
    arm turns slack / HOLE_STATION, and the stud, PIN_STATION from P on the
    same line, falls PIN_STATION * cos per radian."""
    turn = slack_along / HOOK.HOLE_STATION
    return turn * ARM.PIN_STATION * math.cos(_LATCH_THETA)


# --- The MHA-VN-041 sheet's installation line ------------------------------------
# The purchased sheet prints the registry's ``installation_notes``; the
# drawing test holds that field equal to this text.
# Named exception: MHA-VN-041 engagement (drawing-simplicity-policy.md, "Named exceptions").
PIVOT_SCREW_INSTALLATION_NOTES = (
    "INSTALLATION - THROUGH MHA-PD-020 AND MHA-PD-018 INTO THE MHA-PD-007 BLIND TAP.\n"
    f"{PIVOT.THREAD} THREAD ENGAGEMENT {PIVOT_ENGAGEMENT_NOMINAL_D:.2f}D NOMINAL, "
    f"{PIVOT_ENGAGEMENT_WORST_PRINTED:.2f}D MIN.\n"
    "USE LOW-STRENGTH THREADLOCKER."
)
