r"""The hanger's screwed joints and pivot play, judged at the printed bands.

PURE DATA, no SolidWorks/COM imports.  The two purchased screws' catalog
modules stay free of their mates (their stock builds rebuild only when the
catalog changes); this module reads both sides of each joint and holds the
sheet text the MHA-168 purchased sheet prints.  The paper-drive assembly
may import it; no part build does.

* MHA-168 pivot screw (91829A205) in the MHA-074 bar's blind #8-32 tap:
  the 3/16 stock thread is in the tap, but the vendor's thread neck under
  the shoulder's end face leaves full thread only below FULL_THREAD_START;
  worst = that - one pitch (first thread).  The tap's entry countersink lies
  inside the neck zone and costs nothing more (contract §7, ruling R9-7).
  Approved below 1.5 D (the named exception).
* MHA-166 plate screws (91790A194) in the MHA-164 arm's through #8-32 taps:
  the bevel top sits flush with the MHA-165 plate's rear face, so the thread
  in the arm is the length less the plate's over-arm section.
* The pivot head's end play in the arm's spot face: shoulder - spacer -
  spot-face floor (from the arm's front face).
* The MHA-169 latch pin pressed to the floor of the arm's blind end-face
  hole (R9-12): the hole's reamed band keeps the press, its depth band sets
  the proud range, and the shallowest hole still grips the pin 1.5 D.
"""

from __future__ import annotations

import math

import support_bar_spec as BAR
import transgear_arm_geometry as ARM
import transgear_arm_plate_geometry as PLATE
import transgear_arm_plate_screw_spec as PLATE_SCREW
import transgear_pivot_screw_spec as PIVOT
import transgear_latch_pin_spec as LATCH_PIN
import transgear_pivot_spacer_spec as SPACER

ENGAGEMENT_TARGET_D = 1.5


def _floor2(value: float) -> float:
    """A MIN never rounds up: floor to two places."""
    return math.floor(value * 100.0 + 1e-9) / 100.0


# --- MHA-168 pivot screw in the bar -----------------------------------------
if PIVOT.THREAD != BAR.PIVOT_TAP_THREAD:
    raise AssertionError("the pivot screw's thread is not the bar's pivot tap")
if BAR.PIVOT_TAP_FULL_THREAD_MIN < PIVOT.THREAD_LEN:
    raise AssertionError("the bar's pivot tap is shorter than the screw's thread")
# The bar tap's 45° entry countersink stays inside the neck zone.
_PIVOT_TAP_CSK_DEPTH = (BAR.PIVOT_TAP_CSK_DIA - PIVOT.THREAD_MAJOR) / 2.0
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
        f"MHA-168 worst engagement {PIVOT_ENGAGEMENT_WORST_D:.3f}D left the "
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

# --- Pivot head play: shoulder - spacer - spot-face floor --------------------
HEAD_PLAY_NOMINAL = PIVOT.SHOULDER_LEN - SPACER.LENGTH - ARM.SPOT_FACE_FLOOR_FROM_FRONT
HEAD_PLAY_MIN = (
    PIVOT.SHOULDER_LEN
    + PIVOT.SHOULDER_LEN_LIMITS[0]
    - (SPACER.LENGTH + SPACER.LENGTH_BAND)
    - (ARM.SPOT_FACE_FLOOR_FROM_FRONT + ARM.SPOT_FACE_FLOOR_BAND)
)
HEAD_PLAY_MAX = (
    PIVOT.SHOULDER_LEN
    + PIVOT.SHOULDER_LEN_LIMITS[1]
    - (SPACER.LENGTH - SPACER.LENGTH_BAND)
    - (ARM.SPOT_FACE_FLOOR_FROM_FRONT - ARM.SPOT_FACE_FLOOR_BAND)
)
if not 0.0 < HEAD_PLAY_MIN <= HEAD_PLAY_NOMINAL <= HEAD_PLAY_MAX:
    raise AssertionError("the pivot head can clamp the arm")
# Head in the spot face; the shoulder in the arm and spacer bores.
HEAD_RADIAL_CLEARANCE = (ARM.SPOT_FACE_DIA - PIVOT.HEAD_DIA) / 2.0
SHOULDER_RADIAL_CLEARANCE = (
    ARM.PIVOT_BORE_DIA - PIVOT.SHOULDER_DIA - PIVOT.SHOULDER_DIA_LIMITS[1]
) / 2.0
if HEAD_RADIAL_CLEARANCE <= 0.0 or SHOULDER_RADIAL_CLEARANCE <= 0.0:
    raise AssertionError("the pivot screw binds in the arm")
if abs(SPACER.BORE_DIA - ARM.PIVOT_BORE_DIA) > 1e-9:
    raise AssertionError("the spacer and the arm no longer share the running bore")

# --- MHA-166 plate screws in the arm ------------------------------------------
if PLATE_SCREW.THREAD != ARM.PLATE_TAP_SPEC.size:
    raise AssertionError("the plate screws' thread is not the arm's plate tap")
if abs(PLATE_SCREW.HEAD_DIA - PLATE.CSK_DIA) > 1e-9:
    raise AssertionError("the plate's countersink is not the oval head's Ø")
if PLATE_SCREW.HEAD_ANGLE_DEG != PLATE.CSK_ANGLE_DEG:
    raise AssertionError("the plate's countersink angle is not the head's")
_PLATE_TAP_CSK_LOSS = (ARM.PLATE_TAP_CSK_DIA - PLATE_SCREW.THREAD_MAJOR) / 2.0
# A countersink cut large or small by its printed band seats the oval head
# sunk or proud of the plate's rear face by this much.
PLATE_SCREW_SEAT_SHIFT = (
    PLATE.CSK_DIA_BAND / 2.0 / math.tan(math.radians(PLATE.CSK_ANGLE_DEG / 2.0))
)
PLATE_SCREW_ENGAGEMENT_NOMINAL = min(
    PLATE_SCREW.LENGTH - PLATE.THICKNESS_OVER_ARM, ARM.THICKNESS
)
# Thick plate, head proud: the tip is inside the arm, so the first thread
# counts against it.  Thin plate and thin arm stock: the tip is proud of the
# front face, and the arm's two tap countersinks bound the thread instead.
PLATE_SCREW_ENGAGEMENT_WORST = min(
    PLATE_SCREW.LENGTH
    - (PLATE.THICKNESS_OVER_ARM + PLATE.BAND_XX)
    - PLATE_SCREW_SEAT_SHIFT
    - PLATE_SCREW.FIRST_THREAD_LOSS
    - _PLATE_TAP_CSK_LOSS,
    ARM.THICKNESS - ARM.THICKNESS_BAND - 2.0 * _PLATE_TAP_CSK_LOSS,
)
PLATE_SCREW_ENGAGEMENT_NOMINAL_D = (
    PLATE_SCREW_ENGAGEMENT_NOMINAL / PLATE_SCREW.THREAD_MAJOR
)
PLATE_SCREW_ENGAGEMENT_WORST_D = PLATE_SCREW_ENGAGEMENT_WORST / PLATE_SCREW.THREAD_MAJOR
if PLATE_SCREW_ENGAGEMENT_WORST_D < ENGAGEMENT_TARGET_D:
    raise AssertionError(
        f"MHA-166 worst engagement {PLATE_SCREW_ENGAGEMENT_WORST_D:.3f}D < 1.5D"
    )
# The tip ends short of (positive) or proud of (negative) the arm's front face.
PLATE_SCREW_TIP_INSIDE_NOMINAL = ARM.THICKNESS - (
    PLATE_SCREW.LENGTH - PLATE.THICKNESS_OVER_ARM
)
# Furthest the tip can stand proud of the arm's front face (thin plate, thin
# arm stock, head sunk): the assembly holds the lock-station sweep clear of
# this.
PLATE_SCREW_TIP_PROUD_MAX = (
    PLATE_SCREW.LENGTH
    + PLATE_SCREW_SEAT_SHIFT
    - (PLATE.THICKNESS_OVER_ARM - PLATE.BAND_XX)
    - (ARM.THICKNESS - ARM.THICKNESS_BAND)
)

# --- MHA-169 latch pin pressed to the floor of the arm's end-face hole ---------
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
# The depth's .XX band moves the pressed pin's tip by as much: 12.49 .. 13.51.
# The integrator judges the latch hook's grip on the pin over this range.
LATCH_PIN_PROUD_RANGE = (
    LATCH_PIN.proud_length(ARM.PIN_HOLE_DEPTH + ARM.PIN_HOLE_DEPTH_BAND),
    LATCH_PIN.proud_length(ARM.PIN_HOLE_DEPTH - ARM.PIN_HOLE_DEPTH_BAND),
)
# The shallowest hole: (6.05 - 0.51) - 0.443 = 5.10 of full diameter, 1.61 D.
LATCH_PIN_ENGAGEMENT_WORST_D = LATCH_PIN.press_engagement_d(
    ARM.PIN_HOLE_DEPTH - ARM.PIN_HOLE_DEPTH_BAND
)
if LATCH_PIN_ENGAGEMENT_WORST_D < LATCH_PIN.PRESS_ENGAGEMENT_MIN_D:
    raise AssertionError(
        f"the shallowest arm hole grips the latch pin"
        f" {LATCH_PIN_ENGAGEMENT_WORST_D:.2f} D, under"
        f" {LATCH_PIN.PRESS_ENGAGEMENT_MIN_D} D"
    )

# --- The MHA-168 sheet's installation line ------------------------------------
# The purchased sheet prints the registry's ``installation_notes``; the
# drawing test holds that field equal to this text.
# Named exception: MHA-168 engagement (drawing-simplicity-policy.md, "Named exceptions").
PIVOT_SCREW_INSTALLATION_NOTES = (
    "INSTALLATION - THROUGH MHA-167 AND MHA-164 INTO THE MHA-074 BLIND TAP.\n"
    f"{PIVOT.THREAD} THREAD ENGAGEMENT {PIVOT_ENGAGEMENT_NOMINAL_D:.2f}D NOMINAL, "
    f"{PIVOT_ENGAGEMENT_WORST_PRINTED:.2f}D MIN.\n"
    "USE LOW-STRENGTH THREADLOCKER."
)
