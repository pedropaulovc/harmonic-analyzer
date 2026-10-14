r"""Pure-data dimensional contract shared by the wheel axle and its drawing.

A plain pin from 3/16 drill rod, pressed into the mg-wheel-bar's reamed bore
until its shank-to-thread step stands a gauge length off the bar's FRONT face;
the back end then lands near the back face (eight-views-6 shows only a point
there). The magnifying wheel runs on the shank; the front end is
a #4-40 thread for the nut and locknut, finished with a domed tip.
``mg_wheel_group`` sizes the lengths against the whole stack.

Part frame: pin axis local +Y, origin on the bar's FRONT face (the
assembly's d = 0); the pin runs y = BACK_Y (back end) .. TIP_Y.
"""

from __future__ import annotations

import mg_wheel_bar_geom as _bar
from _inch import inch
from _gtol_cylinder import CylinderFace
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

MM_PER_IN = 25.4

PIN_DIA = 0.1875 * MM_PER_IN  # 4.7625, 3/16 drill rod as supplied
PIN_DIA_TOL = 0.005
# The shank reads from the step (the press gauge's face, the drawing's
# dimension origin) to the back end, and only places that end: nothing stands
# behind the bar's back face within 10 mm of the axle (the nearest part, the
# pen-hanger screw head, sits 56 mm along the bar), so it prints .X and the
# back end lands in the window below.
SHANK_LEN = inch(1 + 3 / 16)  # was 28.4; back end nominally flush with the back face
SHANK_LEN_PLACES = 1
THREAD = "#4-40"
THREAD_CALLOUT = "#4-40 UNC"
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]  # 2.845, modelled at the basic major
THREAD_PITCH = MM_PER_IN / 40.0  # 0.635
# Incomplete threads (drawing-guidelines.md rule 18 (thread engagement) counts full thread only): the
# die cutting up to the step leaves 1.5 pitches of run-out there; the dome
# cuts the last pitch short (the tip-chamfer allowance the filing stud takes).
DIE_RUNOUT = 1.5 * THREAD_PITCH  # 0.9525
TIP_INCOMPLETE = THREAD_PITCH  # 0.635
# Step to thread end. The step is the gauged face the nut stack hangs off,
# so the thread reads from it (drawing-guidelines.md rule 10 (dimension from a real feature)'s functional datum) and the
# shank's band stays out of the thread's stack. ±0.25 is the user's option
# (c) of 2026-10-12: 8.17 is the shortest .XX length whose FULL thread still
# clears the locknut's outer face at the worst corner, and its long corner
# leaves at most 2.9 of thread past the locknut (mg_wheel_group). All-inch:
# .320 in decimal (was 8.17): the stack window is 8.068..8.163 with the 13/16
# hub and gauge, narrower than any fraction step.
THREAD_LEN = inch(0.320)
THREAD_LEN_BAND = (0.25, -0.25)
DOME_H = inch(1, 32)  # was 0.8 (1/32: sub-1/4 feature)
PIN_LEN = SHANK_LEN + THREAD_LEN + DOME_H  # 39.084, a reference: the dome sets it
# The spherical tip through the thread-major edge, DOME_H high.
DOME_R = ((THREAD_MAJOR / 2.0) ** 2 + DOME_H**2) / (2.0 * DOME_H)  # 1.672

# The press gauge: the step stands this far off the bar's front face, so the
# bar's depth leaves the stack on the pin (mg_wheel_group).
PRESS_GAUGE = inch(13, 16)  # was 19.5
PRESS_GAUGE_TOL = 0.05

# Where the back end lands on the bar's back face: the shank and the gauge
# from the step, the bar's printed depth from the front face.
_SHANK_TOL = printed_band_mm(SHANK_LEN_PLACES)
BACK_END_PROUD_MAX = (
    (SHANK_LEN + _SHANK_TOL)
    - (PRESS_GAUGE - PRESS_GAUGE_TOL)
    - (_bar.BAR_DEPTH + _bar.BAR_DEPTH_BAND[1])
)  # 0.75
BACK_END_SUNK_MAX = (_bar.BAR_DEPTH + _bar.BAR_DEPTH_BAND[0]) - (
    (SHANK_LEN - _SHANK_TOL) - (PRESS_GAUGE + PRESS_GAUGE_TOL)
)  # 0.95

STEP_Y = PRESS_GAUGE  # 20.6375
BACK_Y = STEP_Y - SHANK_LEN  # -9.525: flush with the bar's back face
THREAD_END_Y = STEP_Y + THREAD_LEN  # 28.7655
TIP_Y = THREAD_END_Y + DOME_H  # 29.55925
# Full thread runs from the die's runout at the step to one pitch short of
# the dome.
FULL_THREAD_START_Y = STEP_Y + DIE_RUNOUT  # 21.59
FULL_THREAD_END_Y = THREAD_END_Y - TIP_INCOMPLETE  # 28.1305

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "ShankLength", "ThreadLength", "PinLength", "DomeR"},
}
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("PinProfile", "ThreadLength"): THREAD_LEN_BAND,
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {
        "PinDia": 4,
        "ShankLength": SHANK_LEN_PLACES,
        "ThreadLength": 2,
        "PinLength": 1,
        "DomeR": 2,
    },
}
# The overall is the shank, the thread and the dome summed: a reference.
REFERENCE_DIMENSIONS = frozenset({"PinLength"})

# The bar's reamed bore the pin presses into, its limits printed to three
# places on the pin's own Ø callout (drawing-guidelines.md rule 7 (notes: few, flagged, never a method); mg_wheel_group.BAR_PRESS
# proves the interference at both corners).
BAR_BORE_LIMITS = (
    _bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[1],
    _bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[0],
)
# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the note says only that the axle presses to the gauge and why. The
# gauge itself is a model dimension of the mg-magnifier assembly, printed on
# MHA-MG-000's AXLE AS PRESSED detail (mg_magnifier_assembly_spec): its 0.10
# is spent inside the thread-end window (mg_wheel_group: full thread under the
# locknut at the thick-stack corner).
# The back end's window, now loose, rides the bar's depth callout.
DRAWING_NOTES = "\n".join(
    (
        "PRESS INTO MG-WHEEL-BAR TO THE GAUGE ON MHA-MG-000 (AXLE AS PRESSED),",
        "SO THE LOCKNUT SITS ON FULL THREAD; RED LOCTITE 271 OPTIONAL.",
    )
)
# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the magnifying wheel runs on the shank, a shaft-in-bushing journal,
# so the one Ø3/16 face carries the machined grade (its pressed length in the
# bar is the same face).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("mg_axle_journal", MACHINED_UM, CylinderFace(PIN_DIA)),
)
