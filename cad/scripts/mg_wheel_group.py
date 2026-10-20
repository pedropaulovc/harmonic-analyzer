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
from _printed_tolerance import printed_band_mm
from _recording_geometry import PEN_Z_MID
from _mg_wheel_rim_geometry import RIM_WIRE_R

# --- the endshake: set at assembly with the nut, by feeler ------------------------
ENDSHAKE = 0.10  # modelled
ENDSHAKE_MIN = 0.05
ENDSHAKE_MAX = 0.15

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
# (mg_wheel_axle_spec.BACK_END_PROUD_MAX / BACK_END_SUNK_MAX). The spacer
# stands between the bar and the hub, so its band is.
_SPACER = (
    _spacer.LENGTH - _spacer.LENGTH_BAND,
    _spacer.LENGTH + _spacer.LENGTH_BAND,
)
_GAUGE = (
    _pin.PRESS_GAUGE - _pin.PRESS_GAUGE_TOL,
    _pin.PRESS_GAUGE + _pin.PRESS_GAUGE_TOL,
)
_BACK = (_back.THICKNESS_MIN, _back.THICKNESS_MAX)
_HUB = (
    _wheel.HUB_LEN + _wheel.HUB_LEN_BAND[1],
    _wheel.HUB_LEN + _wheel.HUB_LEN_BAND[0],
)
# Step to thread end: printed from the gauged step itself, so its own band
# is the whole of it (the shank's tolerance only places the back end).
_THREAD = (
    _pin.THREAD_LEN + _pin.THREAD_LEN_BAND[1],
    _pin.THREAD_LEN + _pin.THREAD_LEN_BAND[0],
)  # 7.95 .. 8.45
_FRONT = (_front.THICKNESS_MIN, _front.THICKNESS_MAX)
_NUTS = (2.0 * _nut.THICKNESS_MIN, 2.0 * _nut.THICKNESS_MAX)

# (a) The pin's shank-to-thread step stays inside the hub's front face, so the
# wheel runs on the full shank and the front washer sits on the thread.
STEP_INSIDE_HUB = (_SPACER[0] + _BACK[0] + _HUB[0]) - _GAUGE[1]  # 0.657
# (b) The locknut sits on FULL thread (drawing-guidelines.md rule 18 (thread engagement) counts full threads only): the
# thread less the incomplete pitch the dome cuts runs past its outer face,
# and the first nut's inner face sits past the die's run-out at the step.
LOCKNUT_THREAD_MARGIN = (_GAUGE[0] + _THREAD[0] - _pin.TIP_INCOMPLETE) - (
    _SPACER[1] + _BACK[1] + _HUB[1] + ENDSHAKE_MAX + _FRONT[1] + _NUTS[1]
)  # 0.002
NUT_RUNOUT_MARGIN = (_SPACER[0] + _BACK[0] + _HUB[0] + ENDSHAKE_MIN + _FRONT[0]) - (
    _GAUGE[1] + _pin.DIE_RUNOUT
)  # 0.211
# (c) At most 2.9 of thread, incomplete pitch included, stands past the
# locknut: the user's option (c) of 2026-10-12, superseding the rev-10
# "dome + 1.3 at every corner" (the washers' and nuts' catalogue bands alone
# put the floor at 2.305 with the thread length exact) and the ~1.46 nominal.
THREAD_PAST_LOCKNUT_LIMIT = 2.9
THREAD_PAST_LOCKNUT_MAX = (_GAUGE[1] + _THREAD[1]) - (
    _SPACER[0] + _BACK[0] + _HUB[0] + ENDSHAKE_MIN + _FRONT[0] + _NUTS[0]
)  # 2.867
THREAD_PAST_LOCKNUT_NOMINAL = _pin.THREAD_END_Y - LOCKNUT_FACE_D  # 1.687
if STEP_INSIDE_HUB <= 0.0:
    raise AssertionError(f"pin step clears the hub front face: {STEP_INSIDE_HUB:.4f}")
if LOCKNUT_THREAD_MARGIN < 0.0:
    raise AssertionError(
        f"locknut runs off the full thread: {LOCKNUT_THREAD_MARGIN:.4f}"
    )
if NUT_RUNOUT_MARGIN < 0.0:
    raise AssertionError(f"nut reaches the die run-out: {NUT_RUNOUT_MARGIN:.4f}")
if THREAD_PAST_LOCKNUT_MAX > THREAD_PAST_LOCKNUT_LIMIT:
    raise AssertionError(
        f"{THREAD_PAST_LOCKNUT_MAX:.4f} of thread past the locknut "
        f"> {THREAD_PAST_LOCKNUT_LIMIT}"
    )
# The thread length's band holds both: its callout on the axle's drawing
# names the gauged step it reads from and states the lower and the upper
# need (drawing-guidelines.md rule 4 (tighten only for function, and name the mate) and drawing-guidelines.md rule 10 (dimension from a real feature)).
THREAD_LENGTH_CALLOUT = (
    "FROM SHANK STEP;\nLOCKNUT ON FULL THREAD,\n"
    f"END {THREAD_PAST_LOCKNUT_LIMIT:.1f} MAX PAST LOCKNUT"
)

# --- fits on the pin ------------------------------------------------------------------
_PIN = (_pin.PIN_DIA - _pin.PIN_DIA_TOL, _pin.PIN_DIA + _pin.PIN_DIA_TOL)
# Press in the bar's reamed bore (interference, both corners > 0).
BAR_PRESS = (
    _PIN[0] - (_bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[0]),
    _PIN[1] - (_bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[1]),
)  # 0.010 .. 0.030
# Matched running fit (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)): the wheel's bore is reamed to this
# diametral clearance on its finished axle, the range the round-15 band gave.
HUB_RUNNING = (0.033, 0.053)
# The largest finished bore: the loosest clearance on the largest pin.
WHEEL_BORE_MAX = _PIN[1] + HUB_RUNNING[1]  # 4.8205
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
# Lever wire: from its drum tangent clockwise down to TIE 1 at 6 o'clock.
# Turning counter-clockwise (pen up: the lever pulls) unwinds it.
LEVER_WIRE_WRAP_DEG = _lever.TANGENT_CLOCK_DEG - _wheel.TIE1_CLOCK_DEG  # 105.8
LEVER_WIRE_WRAP_LEFT_DEG = LEVER_WIRE_WRAP_DEG - CCW_MAX_DEG  # 58.8
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
# twisted turn beside it (1.5 wire dia from the hole centre).
TAIL_ENVELOPE_R = 1.5 * _lever.WIRE_DIA + _wheel.TIE_POSITION_TOL
_STACK_OD_MAX = max(
    _back.OD, _spacer.OD + printed_band_mm(_spacer.OD_PLACES)
)  # 11.8, the spacer at its .X limit
TAIL_STACK_CLEARANCE = _wheel.TIE1_R - TAIL_ENVELOPE_R - _STACK_OD_MAX / 2.0  # 2.7
if TAIL_STACK_CLEARANCE <= 0.0:
    raise AssertionError(
        f"TIE 1 tail reaches the back washer or spacer: {TAIL_STACK_CLEARANCE:.3f}"
    )
