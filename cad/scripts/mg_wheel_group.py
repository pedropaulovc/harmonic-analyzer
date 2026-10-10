r"""Magnifying-wheel group: the axial stack on the wheel axle and the wheel's
rotation range, asserted at import.

PURE DATA + math, no SolidWorks/COM and no drawing imports.
``build_mg_magnifier_assembly`` imports the stations from here, so any part
edit that breaks the stack fails the assembly at import.

Axial stations ``d`` run from the wheel bar's FRONT face toward the pen
(machine z = BAR_FRONT_Z - d): bar -9..0, back washer, wheel hub (spokes'
mid-plane at d 8), endshake, front washer, nut, locknut, then the pin's thread
end and domed tip. The pin is flush with the bar's back face.
"""

from __future__ import annotations

import math

import mg_lever_wire_geom as _lever
import mg_magnifying_wheel_geom as _wheel
import mg_wheel_axle_spec as _pin
import mg_wheel_bar_geom as _bar
import vn_wheel_axle_back_washer_spec as _back
import vn_wheel_axle_front_washer_spec as _front
import vn_wheel_axle_nut_spec as _nut

BAR_FRONT_Z = -138.9  # the wheel bar's front face (build_mg_magnifier_assembly)

# --- the endshake: set at assembly with the nut, by feeler ------------------------
ENDSHAKE = 0.10  # modelled
ENDSHAKE_MIN = 0.05
ENDSHAKE_MAX = 0.15

# --- nominal stations (d) ------------------------------------------------------------
BACK_WASHER_D = 0.0
HUB_BACK_D = BACK_WASHER_D + _back.MODEL_THICKNESS  # 0.91
SPOKE_MID_D = HUB_BACK_D + _wheel.HUB_BACK_Z  # 8.0
HUB_FRONT_D = HUB_BACK_D + _wheel.HUB_LEN  # 20.51
FRONT_WASHER_D = HUB_FRONT_D + ENDSHAKE  # 20.61
NUT_D = FRONT_WASHER_D + _front.MODEL_THICKNESS  # 21.25
LOCKNUT_D = NUT_D + _nut.THICKNESS  # 23.631
LOCKNUT_FACE_D = LOCKNUT_D + _nut.THICKNESS  # 26.013
WHEEL_MID_Z = round(BAR_FRONT_Z - SPOKE_MID_D, 6)  # -146.9
if not math.isclose(SPOKE_MID_D, 8.0):
    raise AssertionError(
        f"spoke mid-plane moved to d {SPOKE_MID_D}; the pen line is at 8"
    )
if not math.isclose(-_pin.BACK_Y, _bar.BAR_DEPTH):
    raise AssertionError("the pin's back end must be flush with the bar's back face")

# --- stack corners (the printed and catalogue bands) -----------------------------------
_BAR_DEPTH = (_bar.BAR_DEPTH - 0.10, _bar.BAR_DEPTH + 0.10)
_BACK = (_back.THICKNESS_MIN, _back.THICKNESS_MAX)
_HUB = (
    _wheel.HUB_LEN + _wheel.HUB_LEN_BAND[1],
    _wheel.HUB_LEN + _wheel.HUB_LEN_BAND[0],
)
_SHANK = (
    _pin.SHANK_LEN + _pin.SHANK_LEN_BAND[1],
    _pin.SHANK_LEN + _pin.SHANK_LEN_BAND[0],
)
_THREAD_END = (
    _pin.THREAD_END + _pin.THREAD_END_BAND[1],
    _pin.THREAD_END + _pin.THREAD_END_BAND[0],
)
_FRONT = (_front.THICKNESS_MIN, _front.THICKNESS_MAX)
_NUTS = 2.0 * _nut.THICKNESS

# (a) The pin's shank-to-thread step stays inside the hub's front face, so the
# wheel runs on the full shank and the front washer sits on the thread.
STEP_INSIDE_HUB = (_BACK[0] + _HUB[0]) - (-_BAR_DEPTH[0] + _SHANK[1])  # 0.587
# (b) The locknut is fully threaded: the thread runs past its outer face.
LOCKNUT_THREAD_MARGIN = (-_BAR_DEPTH[1] + _THREAD_END[0]) - (
    _BACK[1] + _HUB[1] + ENDSHAKE_MAX + _FRONT[1] + _NUTS
)  # 0.033
# (c) Only the dome and a little thread stand past the locknut.
THREAD_PAST_LOCKNUT_LIMIT = 1.35
THREAD_PAST_LOCKNUT_MAX = (-_BAR_DEPTH[0] + _THREAD_END[1]) - (
    _BACK[0] + _HUB[0] + ENDSHAKE_MIN + _FRONT[0] + _NUTS
)  # 1.344
THREAD_PAST_LOCKNUT_NOMINAL = _pin.THREAD_END_Y - LOCKNUT_FACE_D  # 0.687
if STEP_INSIDE_HUB <= 0.0:
    raise AssertionError(f"pin step clears the hub front face: {STEP_INSIDE_HUB:.4f}")
if LOCKNUT_THREAD_MARGIN < 0.0:
    raise AssertionError(f"locknut runs off the thread: {LOCKNUT_THREAD_MARGIN:.4f}")
if THREAD_PAST_LOCKNUT_MAX > THREAD_PAST_LOCKNUT_LIMIT:
    raise AssertionError(
        f"{THREAD_PAST_LOCKNUT_MAX:.4f} of thread past the locknut "
        f"> {THREAD_PAST_LOCKNUT_LIMIT}"
    )

# --- fits on the pin ------------------------------------------------------------------
_PIN = (_pin.PIN_DIA - _pin.PIN_DIA_TOL, _pin.PIN_DIA + _pin.PIN_DIA_TOL)
# Press in the bar's reamed bore (interference, both corners > 0).
BAR_PRESS = (
    _PIN[0] - (_bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[0]),
    _PIN[1] - (_bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[1]),
)  # 0.010 .. 0.030
# Running fit in the wheel's reamed bore (clearance, both corners > 0).
HUB_RUNNING = (
    _wheel.BORE_DIA + _wheel.BORE_BAND[1] - _PIN[1],
    _wheel.BORE_DIA + _wheel.BORE_BAND[0] - _PIN[0],
)  # 0.033 .. 0.053
if min(BAR_PRESS) <= 0.0:
    raise AssertionError(f"pin is not a press fit in the bar: {BAR_PRESS}")
if min(HUB_RUNNING) <= 0.0:
    raise AssertionError(f"wheel does not run free on the pin: {HUB_RUNNING}")
if not (_back.ID > _PIN[1] and _front.ID > _pin.THREAD_MAJOR):
    raise AssertionError("a washer does not pass the pin")
if not _nut.ACROSS_CORNERS / 2.0 < _lever.DRUM_DIA / 2.0:
    raise AssertionError("the nut corners overhang the drum")

# --- rotation range, from the pen's travel over the paper -------------------------------
# The pen hangs on the rim wire, so the rim moves the pen 1:1. Its travel is
# bounded by the recording sheet (build_pd_paper_drive_assembly: sheet y from
# PLATE_Y0 + PLATE_HEIGHT - PAPER_HEIGHT - 3.0 to + PAPER_HEIGHT) about the
# marker tip's rest height (build_pn_pen_assembly.MARKER_POS); the test pins
# these literals to those modules.
MARKER_TIP_REST_Y = 363.25
PAPER_BOTTOM_Y = 324.554
PAPER_TOP_Y = 405.054
PEN_DOWN_MAX = MARKER_TIP_REST_Y - PAPER_BOTTOM_Y  # 38.696
PEN_UP_MAX = PAPER_TOP_Y - MARKER_TIP_REST_Y  # 41.804
# Seen from the front, pen down turns the wheel clockwise (the pen wire leaves
# the groove at 3 o'clock and hangs down); pen up, counter-clockwise.
CW_MAX_DEG = math.degrees(PEN_DOWN_MAX / _wheel.RIM_WIRE_R)  # 45.1
CCW_MAX_DEG = math.degrees(PEN_UP_MAX / _wheel.RIM_WIRE_R)  # 48.7

WRAP_MARGIN_DEG = 30.0  # wire left on its wheel at either end of the travel
# Pen wire: from the 3 o'clock tangent counter-clockwise, up over the top, to
# TIE 2 at 4:30. Turning clockwise unwinds it.
PEN_WIRE_WRAP_DEG = 360.0 + _wheel.TIE2_CLOCK_DEG  # 315
PEN_WIRE_WRAP_LEFT_DEG = PEN_WIRE_WRAP_DEG - CW_MAX_DEG  # 269.9
# Lever wire: from its drum tangent clockwise down to TIE 1 at 6 o'clock.
# Turning counter-clockwise (pen up: the lever pulls) unwinds it.
LEVER_WIRE_WRAP_DEG = _lever.TANGENT_CLOCK_DEG - _wheel.TIE1_CLOCK_DEG  # 107.7
LEVER_WIRE_WRAP_LEFT_DEG = LEVER_WIRE_WRAP_DEG - CCW_MAX_DEG  # 59.0
for _label, _left in (
    ("pen wire", PEN_WIRE_WRAP_LEFT_DEG),
    ("lever wire", LEVER_WIRE_WRAP_LEFT_DEG),
):
    if _left < WRAP_MARGIN_DEG:
        raise AssertionError(
            f"{_label} keeps {_left:.1f} deg of wrap < {WRAP_MARGIN_DEG}"
        )

# TIE 1's tail is twisted off on the hub's back face. It must stay out of the
# wheel bar's band over the whole rotation range: the hole is at 6 o'clock at
# rest, so either turn brings it toward the bar. The tail envelope is the wire
# plus one twisted turn beside it (1.5 wire dia from the hole centre).
TAIL_ENVELOPE_R = 1.5 * _lever.WIRE_DIA + _wheel.TIE_POSITION_TOL
BAR_BAND_HALF = (
    (_bar.BAR_SIDE + _bar.BAR_SIDE_BAND[0]) / 2.0 + _bar.AXLE_BORE_POSITION_TOL
)  # 5.15: the bar's far face from the bore at its worst
TAIL_BAR_CLEARANCE = (
    _wheel.TIE1_R * math.cos(math.radians(max(CW_MAX_DEG, CCW_MAX_DEG)))
    - TAIL_ENVELOPE_R
    - BAR_BAND_HALF
)  # 0.103
if TAIL_BAR_CLEARANCE <= 0.0:
    raise AssertionError(f"TIE 1 tail reaches the wheel bar: {TAIL_BAR_CLEARANCE:.3f}")
