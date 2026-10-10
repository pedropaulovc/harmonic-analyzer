r"""Pure-data dimensional contract shared by the wheel axle and its drawing.

A plain pin from 3/16 drill rod, pressed into the mg-wheel-bar's reamed bore
with its back end flush with the bar's back face (eight-views-6 shows only a
point there). The magnifying wheel runs on the shank; the front end is a
#4-40 thread for the nut and locknut, finished with a domed tip.
``mg_wheel_group`` sizes the length against the whole stack.

Part frame: pin axis local +Y, origin on the bar's FRONT face (the
assembly's d = 0); the pin runs y = -BAR_DEPTH (back end) .. PIN_LEN - BAR_DEPTH.
"""

from __future__ import annotations

from _hole_spec import THREAD_MAJOR_MM
from mg_wheel_bar_geom import BAR_DEPTH

MM_PER_IN = 25.4

PIN_DIA = 0.1875 * MM_PER_IN  # 4.7625, 3/16 drill rod as supplied
PIN_DIA_TOL = 0.005
SHANK_LEN = 28.5  # back end to the thread
SHANK_LEN_BAND = (0.05, -0.05)
THREAD = "#4-40"
THREAD_CALLOUT = "#4-40 UNC"
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]  # 2.845, modelled at the basic major
THREAD_LEN = 7.2
THREAD_END = SHANK_LEN + THREAD_LEN  # 35.7 from the back end
THREAD_END_BAND = (0.05, -0.05)
DOME_H = 0.8
PIN_LEN = THREAD_END + DOME_H  # 36.5
# The spherical tip through the thread-major edge, DOME_H high.
DOME_R = ((THREAD_MAJOR / 2.0) ** 2 + DOME_H**2) / (2.0 * DOME_H)  # 1.665

BACK_Y = -BAR_DEPTH  # the back end, flush with the bar's back face
STEP_Y = BACK_Y + SHANK_LEN  # 19.5
THREAD_END_Y = BACK_Y + THREAD_END  # 26.7
TIP_Y = BACK_Y + PIN_LEN  # 27.5

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "ShankLength", "ThreadEnd", "PinLength", "DomeR"},
}
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("PinProfile", "ShankLength"): SHANK_LEN_BAND,
    ("PinProfile", "ThreadEnd"): THREAD_END_BAND,
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {
        "PinDia": 4,
        "ShankLength": 2,
        "ThreadEnd": 2,
        "PinLength": 1,
        "DomeR": 2,
    },
}

DRAWING_NOTES = "\n".join(
    (
        "PRESS INTO MG-WHEEL-BAR FLUSH WITH THE BACK FACE;",
        "RED LOCTITE 271 OPTIONAL.",
    )
)
