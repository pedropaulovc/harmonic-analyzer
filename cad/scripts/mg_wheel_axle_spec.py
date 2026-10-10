r"""Pure-data dimensional contract shared by the wheel axle and its drawing.

A plain pin from 3/16 drill rod, pressed into the mg-wheel-bar's reamed bore
until its shank-to-thread step stands a gauge length off the bar's FRONT face;
the back end then lands about flush with the back face (eight-views-6 shows
only a point there). The magnifying wheel runs on the shank; the front end is
a #4-40 thread for the nut and locknut, finished with a domed tip.
``mg_wheel_group`` sizes the lengths against the whole stack.

Part frame: pin axis local +Y, origin on the bar's FRONT face (the
assembly's d = 0); the pin runs y = BACK_Y (back end) .. TIP_Y.
"""

from __future__ import annotations

from _hole_spec import THREAD_MAJOR_MM

MM_PER_IN = 25.4

PIN_DIA = 0.1875 * MM_PER_IN  # 4.7625, 3/16 drill rod as supplied
PIN_DIA_TOL = 0.005
# Back end to the step: 0.10 short of the bar's 9.00 depth, so with the press
# gauge and the bar's printed depth the back end stands at most the bar's
# 0.10 band proud of the back face, at most 0.30 sunk (mg_wheel_group).
SHANK_LEN = 28.4
SHANK_LEN_BAND = (0.05, -0.05)
THREAD = "#4-40"
THREAD_CALLOUT = "#4-40 UNC"
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]  # 2.845, modelled at the basic major
# Printed step to thread end: the press gauge is taken at the step, so the
# thread's reach past the nuts reads off this one length.
THREAD_LEN = 7.35
THREAD_LEN_BAND = (0.05, -0.05)
THREAD_END = SHANK_LEN + THREAD_LEN  # 35.75 from the back end
DOME_H = 0.8
PIN_LEN = THREAD_END + DOME_H  # 36.55
# The spherical tip through the thread-major edge, DOME_H high.
DOME_R = ((THREAD_MAJOR / 2.0) ** 2 + DOME_H**2) / (2.0 * DOME_H)  # 1.665

# The press gauge: the step stands this far off the bar's front face, so the
# bar's depth leaves the stack on the pin (mg_wheel_group).
PRESS_GAUGE = 19.5
PRESS_GAUGE_TOL = 0.05

STEP_Y = PRESS_GAUGE  # 19.5
BACK_Y = STEP_Y - SHANK_LEN  # -8.9: 0.10 inside the bar's back face
THREAD_END_Y = STEP_Y + THREAD_LEN  # 26.85
TIP_Y = THREAD_END_Y + DOME_H  # 27.65

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "ShankLength", "ThreadLength", "PinLength", "DomeR"},
}
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("PinProfile", "ShankLength"): SHANK_LEN_BAND,
    ("PinProfile", "ThreadLength"): THREAD_LEN_BAND,
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {
        "PinDia": 4,
        "ShankLength": 2,
        "ThreadLength": 2,
        "PinLength": 2,
        "DomeR": 2,
    },
}

DRAWING_NOTES = "\n".join(
    (
        f"PRESS INTO MG-WHEEL-BAR TO SHANK {PRESS_GAUGE:.2f} +/-{PRESS_GAUGE_TOL:.2f}",
        "FROM FRONT FACE (BACK END ~FLUSH);",
        "RED LOCTITE 271 OPTIONAL.",
    )
)
