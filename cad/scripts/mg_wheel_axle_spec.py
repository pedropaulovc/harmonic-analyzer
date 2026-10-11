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

import mg_wheel_bar_geom as _bar
from _gtol_cylinder import CylinderFace
from _hole_spec import THREAD_MAJOR_MM
from _surface_finish import MACHINED_UM, SurfaceFinishControl

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
THREAD_PITCH = MM_PER_IN / 40.0  # 0.635
# Incomplete threads (drawing-simplicity rule 12 counts full thread only): the
# die cutting up to the step leaves 1.5 pitches of run-out there; the dome
# cuts the last pitch short (the tip-chamfer allowance the filing stud takes).
DIE_RUNOUT = 1.5 * THREAD_PITCH  # 0.9525
TIP_INCOMPLETE = THREAD_PITCH  # 0.635
# Printed step to thread end: the press gauge is taken at the step, so the
# thread's reach past the nuts reads off this one length. 7.97 is the
# shortest .XX length whose FULL thread still clears the locknut's outer face
# at the worst corner (mg_wheel_group).
THREAD_LEN = 7.97
THREAD_LEN_BAND = (0.05, -0.05)
THREAD_END = SHANK_LEN + THREAD_LEN  # 36.37 from the back end
DOME_H = 0.8
PIN_LEN = THREAD_END + DOME_H  # 37.17
# The spherical tip through the thread-major edge, DOME_H high.
DOME_R = ((THREAD_MAJOR / 2.0) ** 2 + DOME_H**2) / (2.0 * DOME_H)  # 1.665

# The press gauge: the step stands this far off the bar's front face, so the
# bar's depth leaves the stack on the pin (mg_wheel_group).
PRESS_GAUGE = 19.5
PRESS_GAUGE_TOL = 0.05

STEP_Y = PRESS_GAUGE  # 19.5
BACK_Y = STEP_Y - SHANK_LEN  # -8.9: 0.10 inside the bar's back face
THREAD_END_Y = STEP_Y + THREAD_LEN  # 27.47
TIP_Y = THREAD_END_Y + DOME_H  # 28.27
# Full thread runs from the die's runout at the step to one pitch short of
# the dome.
FULL_THREAD_START_Y = STEP_Y + DIE_RUNOUT  # 20.4525
FULL_THREAD_END_Y = THREAD_END_Y - TIP_INCOMPLETE  # 26.835

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

# The bar's reamed bore the pin presses into, its limits printed to three
# places on the pin's own Ø callout (policy rule 6; mg_wheel_group.BAR_PRESS
# proves the interference at both corners).
BAR_BORE_LIMITS = (
    _bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[1],
    _bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[0],
)
# Rule 6: the notes say only the press gauge no view can.
DRAWING_NOTES = "\n".join(
    (
        "PRESS INTO MG-WHEEL-BAR UNTIL THE SHANK STEP STANDS",
        f"{PRESS_GAUGE:.2f} +/-{PRESS_GAUGE_TOL:.2f} FROM THE BAR FRONT FACE "
        "(BACK END ~FLUSH);",
        "RED LOCTITE 271 OPTIONAL.",
    )
)
# Rule 5: the magnifying wheel runs on the shank, a shaft-in-bushing journal,
# so the one Ø3/16 face carries the machined grade (its pressed length in the
# bar is the same face).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("mg_axle_journal", MACHINED_UM, CylinderFace(PIN_DIA)),
)
