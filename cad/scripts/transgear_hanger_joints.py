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
* MHA-VN-040 OVAL plate screws (verified1in stock, pre-cut OFF MECHANISM)
  use published ASME head, eccentricity, fillet and thread-length bounds.
  Critical gear-centre/seat controls remain separate; nominal CAD pose is
  not a stock-pin whole-body or positive-load retention certificate.
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
import paper_drive_arm_registration as REGISTRATION
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

# --- Seated spacer face-grade enclosure --------------------------------------
# These are the spacer's geometric grades, conditional on staying seated.
# The source-qualified physical operating-domain proof owns actual masses,
# coupled loads and seat retention; preload/friction proxies do not certify it.
HANGER_TILT = (
    SPACER.REAR_FACE_PERPENDICULARITY + SPACER.FRONT_FACE_PERPENDICULARITY
) / SPACER.FACE_PERPENDICULARITY_ZONE_DIA  # conservative angular enclosure


# Head and spring in the spot face; the arm bore is matched to THIS measured
# shoulder. Stock OD variation is correlated and never added again as play.
# The spring's I.D. may float on the stock shoulder to the spot-face wall.
HEAD_RADIAL_CLEARANCE = (ARM.SPOT_FACE_DIA - PIVOT.HEAD_DIA) / 2.0
SHOULDER_RADIAL_CLEARANCE = ARM.PIVOT_BORE_DIAMETRAL_CLEARANCE[0] / 2.0
PIVOT_RADIAL_FLOAT_MAX = ARM.PIVOT_BORE_DIAMETRAL_CLEARANCE[1] / 2.0
SPRING_RIM_CLEARANCE = (
    ARM.SPOT_FACE_DIA - SPRING.OD - (SPRING.ID - _SHOULDER_MIN)
) / 2.0  # 0.21
if min(HEAD_RADIAL_CLEARANCE, SHOULDER_RADIAL_CLEARANCE, SPRING_RIM_CLEARANCE) <= 0.0:
    raise AssertionError("the pivot screw or its spring binds in the arm")

# --- MHA-VN-040 plate screws in the arm ------------------------------------------
if PLATE_SCREW.THREAD != ARM.PLATE_TAP_SPEC.size:
    raise AssertionError("the plate screws' thread is not the arm's plate tap")
if abs(PLATE_SCREW.HEAD_DIA - PLATE.CSK_DIA) > 1e-9:
    raise AssertionError("the nominal countersink does not match the reference oval head")
if PLATE_SCREW.HEAD_ANGLE_DEG != PLATE.CSK_ANGLE_DEG:
    raise AssertionError("the nominal countersink angle does not match the reference head")
PLATE_SCREW_CUT_PROUD_MAX = 0.2
PLATE_SCREW_THREAD_RADIAL_PLAY_MAX_MM = (
    ARM.PLATE_TAP_PITCH_DIA_LIMITS_MM[1] - PLATE_SCREW.THREAD_PITCH_DIA_LIMITS_MM[0]
) / 2.0
_PLATE_TAP_ENTRY_LOSS = ARM.PLATE_TAP_ENTRY_LOSS_MAX_MM
_PLATE_TAP_EXIT_LOSS = max(ARM.PLATE_TAP_EXIT_LOSS_MAX_MM, PLATE_SCREW.CUT_END_BREAK_MAX)
PLATE_SCREW_INTERNAL_THREAD_SPAN_MIN_MM = (
    ARM.THICKNESS - ARM.THICKNESS_BAND - _PLATE_TAP_ENTRY_LOSS - _PLATE_TAP_EXIT_LOSS
)
# The gear-plane K location is directly controlled. Its finite displacement,
# plus the screw's K-relative radius, bounds the seat-height lever for ANY
# yaw; no pin-end/full-cylinder span or manufactured body-yaw certificate.
_CLAMP_CONTACT_XY_LEVER_MM = (
    math.hypot(ARM.PLATE_SCREW_MID_STATION - PLATE.BORE_STATION, PLATE.BORE_OFFSET)
    + REGISTRATION.REDUCER_AXIS_SETUP_RADIUS_MM
    + REGISTRATION.LOCATOR_GEAR_PLANE_TRAVEL_MAX_MM
    + max(math.hypot(x, y) for x, y in PLATE.SCREW_HOLES)
    + PLATE_SCREW.HEAD_RADIUS_FROM_THREAD_AXIS_MAX_MM
)
PLATE_SCREW_SEAT_HEIGHT_DEBIT_MM = (
    REGISTRATION.ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM
    + _CLAMP_CONTACT_XY_LEVER_MM * math.tan(REGISTRATION.ARM_PLATE_TILT_MAX_RAD)
)
_PLATE_MIN = PLATE.THICKNESS_OVER_ARM - PLATE.THICKNESS_OVER_ARM_BAND
_PLATE_MAX = PLATE.THICKNESS_OVER_ARM + PLATE.THICKNESS_OVER_ARM_BAND
_HEAD_THREAD_AXIAL_MAX = (
    PLATE_SCREW.HEAD_TOP_TO_THREAD_GAGE_MAX_MM + PLATE_SCREW.UNTHREADED_UNDER_HEAD_MAX_MM
)
_HEAD_RADIUS_MAX = PLATE_SCREW.HEAD_RADIUS_FROM_THREAD_AXIS_MAX_MM
_TAP_AXIS_TILT_MAX = math.atan(ARM.REDUCER_POSITION_DIAMETER / ARM.CLAMP_TAP_PROJECTED_HEIGHT_MM)


def _plate_screw_thread_contact_min_mm() -> float:
    """Finite interval contraction from a whole-angle support bound.

    The first full thread is within two published pitches of its GO-ring
    bearing datum. Pay that distinct gage-plane height, eccentric radial
    support, both true seat-height signs and the cut-end/exit overlap. The
    initial support is hypot(A,R) over EVERY acute orientation; subsequent
    contact-span bounds restrict thread tilt by its endpoint pitch-clearance
    disks. Four refinements are outward enclosures, not sampled corners.
    """
    contact = PLATE_SCREW_INTERNAL_THREAD_SPAN_MIN_MM - max(
        0.0, math.hypot(_HEAD_THREAD_AXIAL_MAX, _HEAD_RADIUS_MAX)
        - _PLATE_MIN + PLATE_SCREW_SEAT_HEIGHT_DEBIT_MM,
    )
    for _ in range(4):
        if contact <= 2.0 * PLATE_SCREW_THREAD_RADIAL_PLAY_MAX_MM:
            raise ValueError("published stock has no bounded positive threaded contact span")
        tilt = _TAP_AXIS_TILT_MAX + math.asin(
            2.0 * PLATE_SCREW_THREAD_RADIAL_PLAY_MAX_MM / contact
        )
        support_angle = min(tilt, math.atan2(_HEAD_RADIUS_MAX, _HEAD_THREAD_AXIAL_MAX))
        intrusion = max(
            0.0, _HEAD_THREAD_AXIAL_MAX * math.cos(support_angle)
            + _HEAD_RADIUS_MAX * math.sin(support_angle)
            - _PLATE_MIN + PLATE_SCREW_SEAT_HEIGHT_DEBIT_MM,
        )
        contact = max(contact, PLATE_SCREW_INTERNAL_THREAD_SPAN_MIN_MM - intrusion)
    return contact


PLATE_SCREW_ENGAGEMENT_WORST = _plate_screw_thread_contact_min_mm()
PLATE_SCREW_THREAD_TILT_MAX_RAD = math.asin(
    2.0 * PLATE_SCREW_THREAD_RADIAL_PLAY_MAX_MM / PLATE_SCREW_ENGAGEMENT_WORST
)
PLATE_SCREW_AXIS_TILT_MAX_RAD = PLATE_SCREW_THREAD_TILT_MAX_RAD + _TAP_AXIS_TILT_MAX
# Only a seated BEARING contact must be below these projected-axis caps;
# neither XML serialization nor P14.7 asserts that every crown point is there.
PLATE_SCREW_CONTACT_ARM_LOCAL_Z_MAX_MM = (
    ARM.THICKNESS + ARM.THICKNESS_BAND + _PLATE_MAX + PLATE_SCREW_SEAT_HEIGHT_DEBIT_MM
)
PLATE_SCREW_CONTACT_PLATE_LOCAL_Z_MAX_MM = _PLATE_MAX + PLATE_SCREW_SEAT_HEIGHT_DEBIT_MM
if (PLATE_SCREW_CONTACT_ARM_LOCAL_Z_MAX_MM > ARM.CLAMP_TAP_PROJECTED_HEIGHT_MM
        or PLATE_SCREW_CONTACT_PLATE_LOCAL_Z_MAX_MM > PLATE.CLAMP_PLATE_PROJECTED_HEIGHT_MM):
    raise AssertionError("seated clamp contact exceeds an actually drawn projected-axis height")
# Lo is OVERALL. Correlating it with TOTAL head height removes the unknown
# crown/bevel split without turning .100 REF or .312 nominal into maxima.
# The two extreme points' radial separation includes the complete head cap
# and basic shank radius; no nominal coaxial-head or factory-point credit.
_STOCK_CONTACT_TO_TIP_RADIAL_MAX_MM = (
    _HEAD_RADIUS_MAX + PLATE_SCREW.THREAD_MAJOR / 2.0 + PLATE_SCREW.STOCK_BODY_STRAIGHTNESS_MAX_MM
)
PLATE_SCREW_STOCK_PROUD_MIN = (
    (PLATE_SCREW.STOCK_OVERALL_LENGTH_MIN_MM - PLATE_SCREW.HEAD_WHOLE_METAL_HEIGHT_MAX_MM)
    * math.cos(PLATE_SCREW_AXIS_TILT_MAX_RAD)
    - _STOCK_CONTACT_TO_TIP_RADIAL_MAX_MM * math.sin(PLATE_SCREW_AXIS_TILT_MAX_RAD)
    - (ARM.THICKNESS + ARM.THICKNESS_BAND) - _PLATE_MAX - PLATE_SCREW_SEAT_HEIGHT_DEBIT_MM
)
PLATE_SCREW_STOCK_LEAD_MARGIN_MM = (
    PLATE_SCREW_STOCK_PROUD_MIN - PLATE_SCREW_CUT_PROUD_MAX
    - PLATE_SCREW.POINT_CHAMFER_LENGTH_MAX_MM
)
if PLATE_SCREW_STOCK_LEAD_MARGIN_MM < 0.0:
    raise AssertionError("MHA-VN-040 published-standard stock cannot retain the full-thread cut")
# Separate complete-metal cap, already paying the actual standard fillet;
# do not add the fillet twice or use total O=.152 REF as a maximum.
_WHOLE_HEAD_HEIGHT_MAX_MM = PLATE_SCREW.HEAD_WHOLE_METAL_HEIGHT_MAX_MM
PLATE_SCREW_WHOLE_HEAD_ARM_LOCAL_Z_MAX_MM = (
    PLATE_SCREW_CONTACT_ARM_LOCAL_Z_MAX_MM + _WHOLE_HEAD_HEIGHT_MAX_MM
    + PLATE_SCREW.HEAD_DIA_MAX_MM * math.sin(PLATE_SCREW_AXIS_TILT_MAX_RAD)
)
PLATE_SCREW_WHOLE_HEAD_RADIAL_SUPPORT_MAX_MM = (
    max(_HEAD_RADIUS_MAX, PLATE_SCREW.THREAD_MAJOR / 2.0 + PLATE_SCREW.UNDER_HEAD_FILLET_RADIUS_MAX_MM)
    + _WHOLE_HEAD_HEIGHT_MAX_MM * math.sin(PLATE_SCREW_AXIS_TILT_MAX_RAD)
)
# Native/reference datum pose only. ISO's approximate pin-end dimension
# cannot certify every manufactured body's yaw or this complete entry pose.
PLATE_SCREW_REFERENCE_ENTRY_MARGIN_MM = (
    PLATE.SCREW_HOLE_DIA / 2.0
    - (PLATE_SCREW.THREAD_MAJOR / 2.0 + PLATE_SCREW.UNDER_HEAD_FILLET_RADIUS_MAX_MM)
    / math.cos(_TAP_AXIS_TILT_MAX + REGISTRATION.ARM_PLATE_TILT_MAX_RAD)
    - ARM.REDUCER_POSITION_RADIUS - PLATE.REDUCER_POSITION_RADIUS
)
PLATE_SCREW_ENGAGEMENT_NOMINAL = min(
    PLATE_SCREW.LENGTH - PLATE.THICKNESS_OVER_ARM, ARM.THICKNESS
)
PLATE_SCREW_ENGAGEMENT_NOMINAL_D = PLATE_SCREW_ENGAGEMENT_NOMINAL / PLATE_SCREW.THREAD_MAJOR
PLATE_SCREW_ENGAGEMENT_WORST_D = PLATE_SCREW_ENGAGEMENT_WORST / PLATE_SCREW.THREAD_MAJOR
if PLATE_SCREW_ENGAGEMENT_WORST_D < ENGAGEMENT_TARGET_D:
    raise AssertionError(f"MHA-VN-040 worst engagement {PLATE_SCREW_ENGAGEMENT_WORST_D:.3f}D < 1.5D")
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


def require_arm_plate_joint_inspection(
    *, setup_error_xy_mm: tuple[float, float],
    registration_readings: tuple[REGISTRATION.RegistrationReading, ...],
    required_load_cases: tuple[str, ...], measurement_uncertainty_mm: float,
    own_datum_patterns_accepted: tuple[bool, bool], free_hand_assembly: bool,
) -> tuple[float, float]:
    """Require actual critical S-K setting and signed seat/load readings.

    No commodity receiving records or blanket ALL-parts acceptance boolean.
    Every named applied load and all three signed normal sites are recorded.
    The finite recorded load list is not a continuous retention certificate.
    """
    return REGISTRATION.require_matched_registration(
        setup_error_xy_mm=setup_error_xy_mm, readings=registration_readings,
        required_load_cases=required_load_cases,
        measurement_uncertainty_mm=measurement_uncertainty_mm,
        own_datum_patterns_accepted=own_datum_patterns_accepted,
        free_hand_assembly=free_hand_assembly,
    )


# Graded reference-pose notch clearance only; no unsupported pin-full-span
# manufactured-body yaw inference. Actual gear-plane/seat controls are direct.
NOTCH_REFERENCE_AIR_WORST_MM = (
    (PLATE.NOTCH_RELIEF - PLATE.NOTCH_BAND) * math.cos(ARM.EDGE_LEAN) - ARM.BAND_X
)
if NOTCH_REFERENCE_AIR_WORST_MM <= 0.0:
    raise AssertionError(
        f"MHA-PD-019 reference notch face meets the arm's lower edge: "
        f"{NOTCH_REFERENCE_AIR_WORST_MM:.3f}"
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
# Full radial circle in the worst in-plane load direction; no spacer/head
# friction is credited to shrink it.
_BORE_FLOAT = PIVOT_RADIAL_FLOAT_MAX


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
        lateral = side * ARM.LATCH_PIN_HEIGHT_BAND
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
