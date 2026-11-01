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

import math

import _config
from _column_clamp_interface import BAR_DEPTH
from _fit_deviations import deviations
import mg_wheel_axle_spacer_spec as _spacer
import mg_wheel_bar_geom as _bar
from _gtol_cylinder import CylinderFace
from _hole_spec import THREAD_MAJOR_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl

MM_PER_IN = 25.4
# #290: the axle's sheet prints decimal inch.
UNIT = drawing_unit("parts/mg-wheel-axle", _config.parts("mg-wheel-axle"))

# 3/16 drill rod as supplied: its Ø prints as the stock's REF fraction; the
# supplier's +/-.0002 governs it and sizes the fits (mg_wheel_group).
PIN_DIA = 4.7625  # 3/16
PIN_DIA_TOL = 0.00508  # .0002
PIN_DIA_FRACTION_DENOMINATOR = 16
# The shank reads from the step (the press gauge's face, the drawing's
# dimension origin) to the back end, and only places that end: nothing stands
# behind the bar's back face within 10 mm of the axle (the nearest part, the
# pen-hanger screw head, sits 56 mm along the bar). It grows with the spacer
# (MHA-MG-11) exactly as the gauge does, so the back end stays put; like the
# spacer it follows the pen line, so it keeps its millimetre nominal and
# prints rounded at .XX (the back end's window below reads its printed
# limits).
SHANK_LEN = round(28.4 + _spacer.LENGTH, 6)
SHANK_LEN_PLACES = 2
THREAD = "#4-40"
THREAD_CALLOUT = "#4-40 UNC"
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]  # 2.845, modelled at the basic major
THREAD_PITCH = MM_PER_IN / 40.0  # 0.635
# Incomplete threads (drawing-guidelines.md rule 18 (thread engagement) counts full thread only): a
# die leaves 1.5 pitches of run-out where it stops; the dome cuts the last
# pitch short (the tip-chamfer allowance the filing stud takes).
DIE_RUNOUT = 1.5 * THREAD_PITCH  # 0.9525
TIP_INCOMPLETE = THREAD_PITCH  # 0.635
# ASME B1.1 basic minor (D1 = D - 1.082532 P) and a conservative die root: a
# full basic half-depth under the #4-40 UNC-2A minimum pitch diameter
# (0.0925 in; mg_rod_clamp_joint, the vertical rod's #4-40 relief).
THREAD_BASIC_MINOR = THREAD_MAJOR - 1.082532 * THREAD_PITCH  # 2.158
THREAD_ROOT_2A_MIN = (0.0925 - 0.649519 / 40.0) * MM_PER_IN  # 1.937
# Thread relief at the shank step (drawing-guidelines.md rule 16: a thread
# that runs to a shoulder gets a relief of at least one pitch; the 2026-10-24
# ENFORCE review's blocker). The die's lead runs out in the groove, so full
# thread reaches the groove's far edge. Like the vertical rod's (MHA-MG-04),
# the groove mates with nothing: its Ø and root radius print as single MAX
# limits (swTolMAX prints the model value, so the model IS the limit), its Ø
# under the die's root, both internal corners the grooving tool's nose, R.008
# MAX (the title block's R.040 would not fit the groove). Its width prints as
# a LIMIT pair: the model .043 >= the die's 1.5-pitch lead (.0375) is the
# MAX, held under the first nut's worst-case station off the step
# (mg_wheel_group NUT_RUNOUT_MARGIN; a narrower groove only moves the run-out
# back to the die's lead), and rule 16's one pitch (.025) the MIN, rounded up
# to .028 (codjiflo #1996: a MAX alone accepted a groove under one pitch).
# The title block's .XXX +/-.005 would put the nut on the run-out.
RELIEF_DIA = 1.8542  # .073
RELIEF_WIDTH = 1.0922  # .043
RELIEF_WIDTH_MIN = 0.7112  # .028
RELIEF_ROOT_R = 0.2032  # .008
RELIEF_PLACES = 3
TOL_TYPE_LIMIT = 3  # swTolType_e.swTolLIMIT
TOL_TYPE_MAX = 6  # swTolType_e.swTolMAX
# Full thread starts this far past the step at the latest.
FULL_THREAD_FROM_STEP_MAX = max(RELIEF_WIDTH, DIE_RUNOUT)  # .043
if not RELIEF_DIA <= THREAD_ROOT_2A_MIN < THREAD_BASIC_MINOR < THREAD_MAJOR:
    raise AssertionError("wheel-axle relief Ø leaves thread at the 2A root")
if not THREAD_PITCH <= DIE_RUNOUT <= RELIEF_WIDTH:
    raise AssertionError("wheel-axle relief does not take the die's lead")
if not THREAD_PITCH <= RELIEF_WIDTH_MIN < RELIEF_WIDTH:
    raise AssertionError("wheel-axle relief MIN is under one pitch")
if 2.0 * RELIEF_ROOT_R >= RELIEF_WIDTH_MIN:
    raise AssertionError("wheel-axle relief roots meet across the groove")
# Step to thread end. The step is the gauged face the nut stack hangs off,
# so the thread reads from it (drawing-guidelines.md rule 10 (dimension from a real feature)'s functional datum) and the
# shank's band stays out of the thread's stack. The band is the user's option
# (c) of 2026-10-12 restated in inches: +/-.010 on .323, the shortest length
# whose FULL thread still clears the locknut's outer face at the worst corner
# (the spacer's, gauge's and hub's printed bands in the stack), and whose long
# corner leaves at most .114 of thread past the locknut (the ruled 2.9,
# floored to the inch grid; mg_wheel_group), measured from the thread end
# (the dome's tangent), not the dome's tip.
THREAD_LEN = 8.2042  # .323
THREAD_LEN_BAND = (0.254, -0.254)  # +/-.010
THREAD_LEN_PLACES = 3
THREAD_PAST_LOCKNUT_LIMIT = 2.8956  # .114
# The spherical tip through the thread-major edge: its R prints .XX, the
# height follows from it.
DOME_R = 1.778  # .07
DOME_H = DOME_R - math.sqrt(DOME_R**2 - (THREAD_MAJOR / 2.0) ** 2)  # .028
PIN_LEN = SHANK_LEN + THREAD_LEN + DOME_H  # a reference: the dome sets it

# The press gauge: the step stands this far off the bar's front face, so the
# bar's depth leaves the stack on the pin (mg_wheel_group). The spacer
# (MHA-MG-11) stands between the bar and the back washer, so the gauge is its
# length plus the rev-10 19.5 the washer, hub and nut stack need, snapped to
# the .XXX MHA-MG-00 prints it at (+/-.002): 1.500.
PRESS_GAUGE_PLACES = 3
PRESS_GAUGE = round(
    round((19.5 + _spacer.LENGTH) / MM_PER_IN, PRESS_GAUGE_PLACES) * MM_PER_IN, 6
)
PRESS_GAUGE_TOL = 0.0508  # .002
PRESS_GAUGE_LIMITS = (PRESS_GAUGE - PRESS_GAUGE_TOL, PRESS_GAUGE + PRESS_GAUGE_TOL)

# Where the back end lands on the bar's back face: the shank and the gauge
# from the step, the bar's printed depth from the front face. At every corner
# it stands sunk in the bore, never proud.
_SHANK = printed_deviations(SHANK_LEN, SHANK_LEN_PLACES, unit=UNIT)
_DEPTH = printed_deviations(
    BAR_DEPTH, _bar.BAR_DEPTH_PLACES, deviations(_bar.BAR_DEPTH_BAND), unit=_bar.UNIT
)
BACK_END_SUNK_MIN = (BAR_DEPTH + _DEPTH[0]) - (
    (SHANK_LEN + _SHANK[1]) - PRESS_GAUGE_LIMITS[0]
)  # .008
BACK_END_SUNK_MAX = (BAR_DEPTH + _DEPTH[1]) - (
    (SHANK_LEN + _SHANK[0]) - PRESS_GAUGE_LIMITS[1]
)  # .040
if BACK_END_SUNK_MIN < 0.0:
    raise AssertionError("wheel-axle back end stands proud of the bar")

STEP_Y = PRESS_GAUGE
BACK_Y = STEP_Y - SHANK_LEN  # -8.91: 0.59 inside the 9.5 bar's back face
THREAD_END_Y = STEP_Y + THREAD_LEN
TIP_Y = THREAD_END_Y + DOME_H
# Full thread runs from the relief's far edge to one pitch short of the dome.
FULL_THREAD_START_Y = STEP_Y + RELIEF_WIDTH
FULL_THREAD_END_Y = THREAD_END_Y - TIP_INCOMPLETE

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {
        "PinDia",
        "ShankLength",
        "ThreadLength",
        "PinLength",
        "DomeR",
        "ReliefWidth",
        "ReliefDia",
    },
    "ReliefRoots": {"ReliefRootR"},
}
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("PinProfile", "ThreadLength"): THREAD_LEN_BAND,
}
# The relief's Ø and root radius print as single MAX limits (model value =
# limit); its width as a LIMIT pair, (MIN, MAX) mm, the model at the MAX.
SINGLE_LIMITS: dict[tuple[str, str], tuple[float, int]] = {
    ("PinProfile", "ReliefDia"): (RELIEF_DIA, TOL_TYPE_MAX),
    ("ReliefRoots", "ReliefRootR"): (RELIEF_ROOT_R, TOL_TYPE_MAX),
}
LIMIT_PAIRS: dict[tuple[str, str], tuple[float, float]] = {
    ("PinProfile", "ReliefWidth"): (RELIEF_WIDTH_MIN, RELIEF_WIDTH),
}
# Inch places; the overall reference and the dome R .XX. The sheet dresses the
# stock Ø as its exact fraction (draw_mg_wheel_axle._pin_stock_reference).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {
        "PinDia": 2,
        "ShankLength": SHANK_LEN_PLACES,
        "ThreadLength": THREAD_LEN_PLACES,
        "PinLength": 2,
        "DomeR": 2,
        "ReliefWidth": RELIEF_PLACES,
        "ReliefDia": RELIEF_PLACES,
    },
    "ReliefRoots": {"ReliefRootR": RELIEF_PLACES},
}


def _prints_as_authored(value_mm: float, places: int) -> bool:
    """``value_mm`` is exactly its inch value at ``places``."""
    inches = value_mm / MM_PER_IN
    return math.isclose(round(inches, places), inches, rel_tol=0.0, abs_tol=1e-9)


for (_feature, _name), (_limit, _type) in SINGLE_LIMITS.items():
    if not _prints_as_authored(_limit, DRAWING_PRECISION[_feature][_name]):
        raise AssertionError(f"wheel-axle {_name} MAX does not print as its model")
for (_feature, _name), (_low, _high) in LIMIT_PAIRS.items():
    _places = DRAWING_PRECISION[_feature][_name]
    if not (_prints_as_authored(_low, _places) and _prints_as_authored(_high, _places)):
        raise AssertionError(f"wheel-axle {_name} limits do not print as authored")
# The overall is the shank, the thread and the dome summed: a reference.
REFERENCE_DIMENSIONS = frozenset({"PinLength"})

# The bar's reamed bore the pin presses into, its limits printed to four
# places on the pin's own Ø callout (drawing-guidelines.md rule 7 (notes: few, flagged, never a method); mg_wheel_group.BAR_PRESS
# proves the interference at both corners).
BAR_BORE_LIMITS = (
    _bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[1],
    _bar.AXLE_BORE_DIA + _bar.AXLE_BORE_BAND[0],
)
BAR_BORE_PLACES = _bar.AXLE_BORE_PLACES
# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): no general notes. The press to
# the gauge is MHA-MG-00's step and AXLE AS PRESSED detail
# (mg_magnifier_assembly_spec); every requirement here rides its own callout
# (mg_wheel_axle_callouts), and the back end's window rides the bar's depth
# callout.
# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the magnifying wheel runs on the shank, a shaft-in-bushing journal,
# so the one Ø3/16 face carries the machined grade (its pressed length in the
# bar is the same face).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl(
        "mg_axle_journal", MACHINED_UM, CylinderFace(PIN_DIA), display_unit=UNIT
    ),
)
