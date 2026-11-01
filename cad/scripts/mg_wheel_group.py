r"""Magnifying-wheel group: the axial stack on the wheel axle and the wheel's
rotation range, asserted at import.

PURE DATA + math, no SolidWorks/COM and no drawing imports.
``build_mg_magnifier_assembly`` imports the stations from here, so any part
edit that breaks the stack fails the assembly at import.

Axial stations ``d`` run from the wheel bar's FRONT face toward the pen
(machine z = BAR_FRONT_Z - d): bar -9..0, spacer, back washer, wheel hub
(spokes' mid-plane on the pen-rod line ``_recording_geometry.PEN_Z_MID``),
endshake, front washer, nut, locknut, then the pin's thread end and domed tip.
The pin is pressed to a gauge from the bar's front face, its back end about
flush with the back face. The spacer's length is derived from the pen line
(``mg_wheel_axle_spacer_spec``), so the wheel mid-plane is the pen line by
construction; the closure is asserted below.
"""

from __future__ import annotations

import math

import sh_vn_music_wire_lever_geom as _lever
import mg_magnifying_wheel_geom as _wheel
import mg_wheel_axle_spacer_spec as _spacer
import mg_wheel_axle_spec as _pin
import mg_wheel_bar_geom as _bar
import mg_vn_wheel_axle_back_washer_spec as _back
import mg_vn_wheel_axle_front_washer_spec as _front
import mg_vn_wheel_axle_nut_spec as _nut
from _recording_geometry import PEN_Z_MID
from _mg_wheel_rim_geometry import RIM_WIRE_R

# --- the endshake: set at assembly with the nut, by feeler ------------------------
ENDSHAKE = 0.1016  # .004, modelled
ENDSHAKE_MIN = 0.0508  # .002
ENDSHAKE_MAX = 0.1524  # .006

# --- nominal stations (d) ------------------------------------------------------------
SPACER_D = 0.0
BACK_WASHER_D = SPACER_D + _spacer.LENGTH
HUB_BACK_D = BACK_WASHER_D + _back.MODEL_THICKNESS
SPOKE_MID_D = HUB_BACK_D + _wheel.HUB_BACK_Z
HUB_FRONT_D = HUB_BACK_D + _wheel.HUB_LEN
FRONT_WASHER_D = HUB_FRONT_D + ENDSHAKE
NUT_D = FRONT_WASHER_D + _front.MODEL_THICKNESS
LOCKNUT_D = NUT_D + _nut.THICKNESS
LOCKNUT_FACE_D = LOCKNUT_D + _nut.THICKNESS
# The wheel's mid-plane IS the pen-rod line: the pen wire leaves the rim
# groove plumb onto the rod (sh_vn_music_wire_pen_geom).
WHEEL_MID_Z = PEN_Z_MID
_SPOKE_MID_Z = _bar.BAR_FRONT_Z - SPOKE_MID_D
if not math.isclose(_SPOKE_MID_Z, WHEEL_MID_Z, abs_tol=1e-9):
    raise AssertionError(
        f"the stack puts the spokes' mid-plane at z {_SPOKE_MID_Z}, "
        f"off the pen line {WHEEL_MID_Z}"
    )

# --- stack corners (the printed and catalogue bands) -----------------------------------
# The pin is pressed to a gauge from the bar's FRONT face, so the bar's depth
# is not in the stack; it sets only where the back end lands
# (mg_wheel_axle_spec.BACK_END_SUNK_MIN / BACK_END_SUNK_MAX). The spacer
# stands between the bar and the hub, so its band is. The spacer, the gauge
# and the hub keep millimetre nominals and print rounded: each term is its
# printed limits.
_SPACER = _spacer.LENGTH_LIMITS
_GAUGE = _pin.PRESS_GAUGE_LIMITS
_BACK = (_back.THICKNESS_MIN, _back.THICKNESS_MAX)
_HUB = _wheel.HUB_LEN_LIMITS
# Step to thread end: printed from the gauged step itself, so its own band
# is the whole of it (the shank's tolerance only places the back end).
_THREAD = (
    _pin.THREAD_LEN + _pin.THREAD_LEN_BAND[1],
    _pin.THREAD_LEN + _pin.THREAD_LEN_BAND[0],
)  # .313 .. .333
_FRONT = (_front.THICKNESS_MIN, _front.THICKNESS_MAX)
_NUTS = (2.0 * _nut.THICKNESS_MIN, 2.0 * _nut.THICKNESS_MAX)

# (a) The pin's shank-to-thread step stays inside the hub's front face, so the
# wheel runs on the full shank and the front washer sits on the thread.
STEP_INSIDE_HUB = (_SPACER[0] + _BACK[0] + _HUB[0]) - _GAUGE[1]  # .028
# (b) The locknut sits on FULL thread (drawing-guidelines.md rule 18 (thread engagement) counts full threads only): the
# thread less the incomplete pitch the dome cuts runs past its outer face,
# and the first nut's inner face sits past the step's thread relief (or the
# die's run-out, were the relief cut narrower than the die's lead).
LOCKNUT_THREAD_MARGIN = (_GAUGE[0] + _THREAD[0] - _pin.TIP_INCOMPLETE) - (
    _SPACER[1] + _BACK[1] + _HUB[1] + ENDSHAKE_MAX + _FRONT[1] + _NUTS[1]
)  # .000
NUT_RUNOUT_MARGIN = (_SPACER[0] + _BACK[0] + _HUB[0] + ENDSHAKE_MIN + _FRONT[0]) - (
    _GAUGE[1] + _pin.FULL_THREAD_FROM_STEP_MAX
)  # .005
# (c) At most .114 of thread, incomplete pitch included, stands past the
# locknut: the user's option (c) of 2026-10-12 (2.9 mm, floored to the inch
# grid), superseding the rev-10 "dome + 1.3 at every corner" (the washers'
# and nuts' catalogue bands alone set a floor near it with the thread length
# exact).
THREAD_PAST_LOCKNUT_MAX = (_GAUGE[1] + _THREAD[1]) - (
    _SPACER[0] + _BACK[0] + _HUB[0] + ENDSHAKE_MIN + _FRONT[0] + _NUTS[0]
)  # .111
THREAD_PAST_LOCKNUT_NOMINAL = _pin.THREAD_END_Y - LOCKNUT_FACE_D  # .066
if STEP_INSIDE_HUB <= 0.0:
    raise AssertionError(f"pin step clears the hub front face: {STEP_INSIDE_HUB:.4f}")
if LOCKNUT_THREAD_MARGIN < 0.0:
    raise AssertionError(
        f"locknut runs off the full thread: {LOCKNUT_THREAD_MARGIN:.4f}"
    )
if NUT_RUNOUT_MARGIN < 0.0:
    raise AssertionError(f"nut reaches the thread relief: {NUT_RUNOUT_MARGIN:.4f}")
if THREAD_PAST_LOCKNUT_MAX > _pin.THREAD_PAST_LOCKNUT_LIMIT:
    raise AssertionError(
        f"{THREAD_PAST_LOCKNUT_MAX:.4f} of thread past the locknut "
        f"> {_pin.THREAD_PAST_LOCKNUT_LIMIT}"
    )

# --- fits on the pin ------------------------------------------------------------------
_PIN = (_pin.PIN_DIA - _pin.PIN_DIA_TOL, _pin.PIN_DIA + _pin.PIN_DIA_TOL)
# Press in the bar's reamed bore (interference, both corners > 0).
BAR_PRESS = (
    _PIN[0] - (_bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[0]),
    _PIN[1] - (_bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[1]),
)  # .0003 .. .0012
# Running fit (drawing-guidelines.md rule 4 (tighten only for function, and
# name the mate)): the wheel's owned-reamer .1885 bore (+.0005/0) on the
# drill rod's supplier band.
HUB_RUNNING = (0.02032, 0.04318)  # (.0008, .0017)
# The largest finished bore: the loosest clearance on the largest pin.
WHEEL_BORE_MAX = _PIN[1] + HUB_RUNNING[1]  # .1894
if min(BAR_PRESS) <= 0.0:
    raise AssertionError(f"pin is not a press fit in the bar: {BAR_PRESS}")
if min(HUB_RUNNING) <= 0.0:
    raise AssertionError(f"wheel does not run free on the pin: {HUB_RUNNING}")
if not (
    _back.ID > _PIN[1] and _spacer.BORE_DIA > _PIN[1] and _front.ID > _pin.THREAD_MAJOR
):
    raise AssertionError("a washer or the spacer does not pass the pin")
if not _nut.ACROSS_CORNERS / 2.0 < _lever.DRUM_DIA / 2.0:
    raise AssertionError("the nut corners overhang the drum")

# --- rotation range, from the pen's travel over the paper -------------------------------
# The pen hangs on the rim wire, so the rim moves the pen 1:1. Its travel is
# bounded by the recording sheet (build_pd_paper_drive_assembly: sheet y from
# PLATE_Y0 + PLATE_HEIGHT - PAPER_HEIGHT - 3.0 to + PAPER_HEIGHT) about the
# marker tip's rest height (pn_pen_carriage_geom.MARKER_POS, the nib at rest).
# The test pins these literals to those modules; they stay literals so a pen
# or paper-drive part edit does not re-key the magnifier's closure.
MARKER_TIP_REST_Y = 364.705
PAPER_BOTTOM_Y = 324.554
PAPER_TOP_Y = 405.054
PEN_DOWN_MAX = MARKER_TIP_REST_Y - PAPER_BOTTOM_Y  # 40.151
PEN_UP_MAX = PAPER_TOP_Y - MARKER_TIP_REST_Y  # 40.349
# Seen from the front, pen down turns the wheel clockwise (the pen wire leaves
# the groove at 3 o'clock and hangs down); pen up, counter-clockwise.
CW_MAX_DEG = math.degrees(PEN_DOWN_MAX / RIM_WIRE_R)  # 46.8
CCW_MAX_DEG = math.degrees(PEN_UP_MAX / RIM_WIRE_R)  # 47.0

WRAP_MARGIN_DEG = 30.0  # wire left on its wheel at either end of the travel
# Pen wire: from the 3 o'clock tangent counter-clockwise, up over the top, to
# TIE 2 at about 4:30. Turning clockwise unwinds it.
PEN_WIRE_WRAP_DEG = 360.0 + _wheel.TIE2_CLOCK_DEG  # 317
PEN_WIRE_WRAP_LEFT_DEG = PEN_WIRE_WRAP_DEG - CW_MAX_DEG  # 270.2
# Lever wire: from its drum tangent clockwise down to TIE 1 at 8 o'clock.
# Turning counter-clockwise (pen up: the lever pulls) unwinds it.  The wire's
# contact arc is judged at the worst printed case: on the smallest drum (.XX)
# the tangent from the hook lands latest, and the wire leaves the drum
# tangentially to reach TIE 1 standing outboard of it, at the hole's
# farthest axis offset (the wire may lie anywhere in the smallest drilled
# hole's slack), its clock angle shifted by that offset too.
_HOOK_V = (_lever.HOOK_X - _lever.WHEEL_X, _lever.HOOK_Y - _lever.WHEEL_BAR_Y)
_WIRE_R_MIN = _wheel.DRUM_WIRE_R_RANGE[0]
_TANGENT_CLOCK_MIN = 180.0 - math.degrees(
    math.atan2(_HOOK_V[1], _HOOK_V[0]) + math.acos(_WIRE_R_MIN / math.hypot(*_HOOK_V))
)
_TIE1_REACH_MAX = (
    _wheel.TIE1_R
    + _wheel.TIE1_OFFSET_MAX
    - (_wheel.TIE_HOLE_DIA - _lever.WIRE_DIA) / 2.0
)
LEVER_WIRE_DEPARTURE_DEG = math.degrees(
    math.acos(_WIRE_R_MIN / _TIE1_REACH_MAX)
)  # 33.9
_TIE1_CLOCK_SHIFT_DEG = math.degrees(math.asin(_wheel.TIE1_OFFSET_MAX / _wheel.TIE1_R))
LEVER_WIRE_WRAP_DEG = (
    _TANGENT_CLOCK_MIN
    - _wheel.TIE1_CLOCK_DEG
    - LEVER_WIRE_DEPARTURE_DEG
    - _TIE1_CLOCK_SHIFT_DEG
)  # 128.7
LEVER_WIRE_WRAP_LEFT_DEG = LEVER_WIRE_WRAP_DEG - CCW_MAX_DEG  # 81.7
for _label, _left in (
    ("pen wire", PEN_WIRE_WRAP_LEFT_DEG),
    ("lever wire", LEVER_WIRE_WRAP_LEFT_DEG),
):
    if _left < WRAP_MARGIN_DEG:
        raise AssertionError(
            f"{_label} keeps {_left:.1f} deg of wrap < {WRAP_MARGIN_DEG}"
        )

# TIE 1's tail is twisted off on the hub's back face, beside the back washer
# and the spacer behind it (the bar is a spacer's length further back). The
# hole circles the axle as the wheel turns, so the tail must clear the larger
# of the two at every angle: radially. The tail envelope is the wire plus one
# twisted turn beside it (1.5 wire dia from the hole centre), about the hole's
# exit at its farthest axis offset (printed station, angle and drill wander).
TAIL_ENVELOPE_R = 1.5 * _lever.WIRE_DIA + _wheel.TIE1_OFFSET_MAX
_STACK_OD_MAX = max(_back.OD, _spacer.OD_MAX)  # the spacer at its .XX limit
TAIL_STACK_CLEARANCE = _wheel.TIE1_R - TAIL_ENVELOPE_R - _STACK_OD_MAX / 2.0
if TAIL_STACK_CLEARANCE <= 0.0:
    raise AssertionError(
        f"TIE 1 tail reaches the back washer or spacer: {TAIL_STACK_CLEARANCE:.3f}"
    )
