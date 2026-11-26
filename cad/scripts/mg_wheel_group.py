r"""Magnifying-wheel group: the axial stack on the wheel axle and the wheel's
rotation range, asserted at import.

PURE DATA + math, no SolidWorks/COM and no drawing imports.
``build_mg_magnifier_assembly`` imports the stations from here, so any part
edit that breaks the stack fails the assembly at import.

Axial stations ``d`` run from the wheel bar's FRONT face toward the pen
(machine z = BAR_FRONT_Z - d): bar -9..0, spacer, back washer, wheel hub
(spokes' mid-plane on the pen-rod line ``_recording_geometry.PEN_Z_MID``),
endshake, front washer, nut, locknut, then the pin's thread end and domed tip.
The model sets the pin at its nominal station past the spacer's outer face
(the bench sets it to a dry trial of the stack, C11), its back end inside the
bar's bore. The spacer's length is derived from the pen line
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
from _fit_deviations import deviations
from _printed_tolerance import printed_deviations
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

# --- stack corners at the trial (the printed and catalogue bands) ---------------------
# Owner ruling 2026-11-24, fit audit part 2, C11 ("Yes, set to the trial
# stack"): MHA-MG-00 no longer gauges the step, so the old .768 +/-.002
# press gauge is no term here (DETAIL A prints the station REF). The axle
# goes in with its plain end flush and the trial only slides it out, to
# DETAIL B's middle after a short thread end; every corner below runs at
# those two settings. The hub and the spacer keep millimetre nominals and
# print rounded: each term is its printed limits.
_BACK = (_back.THICKNESS_MIN, _back.THICKNESS_MAX)
_HUB = _wheel.HUB_LEN_LIMITS
# Step to thread end: printed from the step itself, so its own band is the
# whole of it.
_THREAD = (
    _pin.THREAD_LEN + _pin.THREAD_LEN_BAND[1],
    _pin.THREAD_LEN + _pin.THREAD_LEN_BAND[0],
)  # .314 .. .334
_FRONT = (_front.THICKNESS_MIN, _front.THICKNESS_MAX)
_NUTS = (2.0 * _nut.THICKNESS_MIN, 2.0 * _nut.THICKNESS_MAX)

# The trial (C11) accepts on things to see, at the go leaf's endshake
# (ENDSHAKE_MIN): the front washer seated on the hub's spigot face with no
# light under it, the first nut ran on full thread down to it, the thread
# end inside DETAIL B (TIP_INCOMPLETE .. THREAD_PAST_LOCKNUT_LIMIT) and the
# plain end not proud. The seat is the shank step inside the hub, read
# directly: the front washer's bore is under the shank's, so a step outside
# the hub's front face grounds the washer on it and shows light. The nut
# check alone does not bound the step (Codjiflo r1 of #3529): full thread
# may start at the relief's MIN width, .028, so a nut on thread over the go
# leaf and the thickest washer leaves the step up to .006 outside the hub.
# TRIAL_STEP_INSIDE_HUB_MIN proves the seat check rejects no conforming set
# at either setting the trial reaches: the flush start (the plain end on the
# plate, the step the shank less the bar's depth off the bar's front face),
# and a slide out to DETAIL B's middle after a short thread end (the step
# then hangs off the nut stack: the thread less that reading, the go leaf,
# the thickest washer and the thickest nuts). The set endshake (up to
# ENDSHAKE_MAX) lowers the thread end by at most TRIAL_ENDSHAKE_DROP and
# never raises it, so the re-read after the locknut can only fall short, and
# closing the endshake to the go leaf restores the trial's reading.
_SHANK_DEV = printed_deviations(_pin.SHANK_LEN, _pin.SHANK_LEN_PLACES, unit=_pin.UNIT)
_DEPTH_DEV = printed_deviations(
    _pin.BAR_DEPTH, _bar.BAR_DEPTH_PLACES, deviations(_bar.BAR_DEPTH_BAND), unit=_bar.UNIT
)
_FLUSH_STEP = (
    (_pin.SHANK_LEN + _SHANK_DEV[0]) - (_pin.BAR_DEPTH + _DEPTH_DEV[1]),
    (_pin.SHANK_LEN + _SHANK_DEV[1]) - (_pin.BAR_DEPTH + _DEPTH_DEV[0]),
)  # 1.461 .. 1.491
_HUB_FRONT = (
    _spacer.LENGTH_LIMITS[0] + _BACK[0] + _HUB[0],
    _spacer.LENGTH_LIMITS[1] + _BACK[1] + _HUB[1],
)  # 1.523 .. 1.557
# The step inside the hub at the flush start; and the slide's target, its
# least step inside the hub hanging off the nut stack.
_FLUSH_INSIDE_MIN = _HUB_FRONT[0] - _FLUSH_STEP[1]  # .032
TRIAL_SLIDE_TARGET = (_pin.TIP_INCOMPLETE + _pin.THREAD_PAST_LOCKNUT_LIMIT) / 2.0  # .0695
_SLID_INSIDE_MIN = (
    _THREAD[0] - TRIAL_SLIDE_TARGET - ENDSHAKE_MIN - _FRONT[1] - _NUTS[1]
)  # .0145
TRIAL_STEP_INSIDE_HUB_MIN = min(_FLUSH_INSIDE_MIN, _SLID_INSIDE_MIN)  # .0145
TRIAL_ENDSHAKE_DROP = ENDSHAKE_MAX - ENDSHAKE_MIN
if TRIAL_STEP_INSIDE_HUB_MIN <= 0.0:
    raise AssertionError(
        f"a conforming trial stack fails the washer seat check: {TRIAL_STEP_INSIDE_HUB_MIN:.4f}"
    )
# The first nut's inner face sits past the latest full-thread start (the
# relief's MAX width, or the die's run-out were the relief cut narrower than
# its lead) at both settings, so a conforming set passes the trial's nut
# check (drawing-guidelines.md rule 18 (thread engagement) counts full
# threads only): at the flush start, the step inside the hub, the go leaf
# and the thinnest washer; slid, the thread less the target and the thickest
# nuts. The set endshake only moves the nut further out.
NUT_RUNOUT_MARGIN = (
    min(
        _FLUSH_INSIDE_MIN + ENDSHAKE_MIN + _FRONT[0],
        _THREAD[0] - TRIAL_SLIDE_TARGET - _NUTS[1],
    )
    - _pin.FULL_THREAD_FROM_STEP_MAX
)  # .0055
if NUT_RUNOUT_MARGIN < 0.0:
    raise AssertionError(f"nut reaches the thread relief: {NUT_RUNOUT_MARGIN:.4f}")
# At most .114 of thread, incomplete pitch included, stands past the locknut:
# the user's option (c) of 2026-10-12 (2.9 mm, floored to the inch grid). The
# trial can only slide the axle out from flush, never push it further in, so
# the flush start's long corner (at the go leaf, ENDSHAKE_MIN, the trial's
# endshake) must already read inside DETAIL B: a conforming set never needs
# the plain end proud. The slide's target is DETAIL B's middle, under it.
# The locknut on full thread is DETAIL B's low limit (TIP_INCOMPLETE), read
# at the trial and again once the endshake is set, each with its remedy.
THREAD_PAST_LOCKNUT_MAX = _THREAD[1] - (
    _FLUSH_INSIDE_MIN + ENDSHAKE_MIN + _FRONT[0] + _NUTS[0]
)  # .108
THREAD_PAST_LOCKNUT_NOMINAL = _pin.THREAD_END_Y - LOCKNUT_FACE_D  # .067
if THREAD_PAST_LOCKNUT_MAX > _pin.THREAD_PAST_LOCKNUT_LIMIT:
    raise AssertionError(
        f"{THREAD_PAST_LOCKNUT_MAX:.4f} of thread past the locknut at the flush "
        f"start > {_pin.THREAD_PAST_LOCKNUT_LIMIT}"
    )

# --- fits on the pin ------------------------------------------------------------------
_PIN = (_pin.PIN_DIA - _pin.PIN_DIA_TOL, _pin.PIN_DIA + _pin.PIN_DIA_TOL)
# Bonded in the bar's 3/16 drilled bore (owner ruling 2026-11-24, fit audit
# question 18): the drill's DRILLED HOLES row over the drill rod's supplier
# band leaves a diametral gap inside LOCTITE 638's. Its tight corner is a
# light press (.0002 at most), which the compound takes as well; the step
# pushes the axle in on its shoulder through the sleeve.
BAR_BOND_GAP = (
    (_bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[1]) - _PIN[1],
    (_bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[0]) - _PIN[0],
)  # -.0002 .. .0042
# Running fit (drawing-guidelines.md rule 4 (tighten only for function, and
# name the mate)): the wheel's .1885 reamed bore (+.0005/0; the reamer is to
# order, shop-equipment tools.reamer-1885) on the
# drill rod's supplier band.
HUB_RUNNING = (0.02032, 0.04318)  # (.0008, .0017)
# The largest finished bore: the loosest clearance on the largest pin.
WHEEL_BORE_MAX = _PIN[1] + HUB_RUNNING[1]  # .1894
if BAR_BOND_GAP[1] > _wheel.LOCTITE_638_GAP_MAX:
    raise AssertionError(f"axle gap in the bar exceeds LOCTITE 638's: {BAR_BOND_GAP}")
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
# hole's slack), its clock angle shifted by that offset too.  The drum-side
# mouth is TIE 1's #50 counter-drill (#2406); the #60's smaller slack keeps
# the wire farther out, so it bounds the departure from above.
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
)  # 30.8
_TIE1_CLOCK_SHIFT_DEG = math.degrees(math.asin(_wheel.TIE1_OFFSET_MAX / _wheel.TIE1_R))
LEVER_WIRE_WRAP_DEG = (
    _TANGENT_CLOCK_MIN
    - _wheel.TIE1_CLOCK_DEG
    - LEVER_WIRE_DEPARTURE_DEG
    - _TIE1_CLOCK_SHIFT_DEG
)  # 131.8
LEVER_WIRE_WRAP_LEFT_DEG = LEVER_WIRE_WRAP_DEG - CCW_MAX_DEG  # 84.8
for _label, _left in (
    ("pen wire", PEN_WIRE_WRAP_LEFT_DEG),
    ("lever wire", LEVER_WIRE_WRAP_LEFT_DEG),
):
    if _left < WRAP_MARGIN_DEG:
        raise AssertionError(
            f"{_label} keeps {_left:.1f} deg of wrap < {WRAP_MARGIN_DEG}"
        )

# TIE 1's tail is knotted round a toggle on the hub's back face, beside the
# back washer and the spacer behind it (the bar is a spacer's length further
# back). A knot in a Ø.008 wire is smaller than the hole, so the tail is
# tied round the middle of a TOGGLE_LENGTH offcut of the same wire, which
# lies across the hole and cannot enter it. The hole circles the axle as
# the wheel turns, so the toggle must clear the larger of the two at every
# angle: radially. The tail envelope is the toggle swung any way about the
# hole's exit at its farthest axis offset (printed station, angle and drill
# wander).
TOGGLE_LENGTH = _lever.TOGGLE_LENGTH
TAIL_ENVELOPE_R = TOGGLE_LENGTH / 2.0 + _wheel.TIE1_OFFSET_MAX
_STACK_OD_MAX = max(_back.OD, _spacer.OD_MAX)  # the spacer at its .XX limit
TAIL_STACK_CLEARANCE = _wheel.TIE1_R - TAIL_ENVELOPE_R - _STACK_OD_MAX / 2.0
if TAIL_STACK_CLEARANCE <= 0.0:
    raise AssertionError(
        f"TIE 1 tail reaches the back washer or spacer: {TAIL_STACK_CLEARANCE:.3f}"
    )
