r"""MHA-PD-24 transgear-rear-bushing: the brass spacer behind the disc cluster (R9-68).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  A turned brass ring on the MHA-PD-23 pin between the MHA-PD-VN-68
shims on the MHA-PD-18 arm's front face and the MHA-PD-10 sleeve's rear face.
Its length only sets the disc's end float, which the shims close at assembly
(owner ruling 2026-11-01, #2124): ``transgear_cluster_fit.REAR_BUSHING_LENGTH``
keeps the unshimmed float over ``transgear_cluster_fit.END_FLOAT_MIN`` at the
worst case at the title block's .XXX, which only moves the shim count.  It
runs free on the pin; the MHA-PD-10 sleeve's rear face turns on its front
face.  #290: the sheet prints decimal inch; every length is the exact
millimetre value of its inch nominal.

Part frame: axis local +Z through the origin (``Axis1``); faces at z = 0
(Front Plane, on the arm's front face) and z = LENGTH (``SleeveFace``, on
the sleeve's rear face).
"""

from __future__ import annotations

import _config
import transgear_cluster_fit as FIT
import pd_transgear_pin_spec as PIN
from _gtol_planar import PlanarFace
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pd_cluster_stack_band import STACK_NAME, STACK_SHEET

UNIT = drawing_unit(
    "parts/pd-transgear-rear-bushing", _config.parts("pd-transgear-rear-bushing")
)

OD = 8.89  # .35
OD_PLACES = 2
# The bore: reamed with the set's .1260 reamer, the sleeve's (one reamer,
# one size), and printed at that size with NO band (rule 4, form 2; the
# modelled cut, +.001, is the owner's ruling of 2026-11-24 on fit audit
# question 5).  BORE_DIA_BAND is the ANALYSIS band the
# reamer is modelled to cut, never printed; the wall and the cocking check
# below read it.
BORE_DIA = FIT.BORE_DIA  # .1260
BORE_DIA_BAND = FIT.BORE_DIA_BAND  # (upper, lower) ANALYSIS deviations
BORE_PLACES = 3
# The callout: size and process, then the mate and that it is turned to
# this bore (a bare fit name is not enough).  The pair's one acceptance
# prints on the sheet of the member made last, the pin's (MHA-PD-23 note
# 1).  Why the bore is reamed (BORE_COCK_TAKE_UP below) is in the part's
# necessity file (owner ruling 2026-11-24: "In the part's registry file,
# not on the sheet"; cad/config/necessity/pd-transgear-rear-bushing.yaml).
BORE_CALLOUT = f"REAM THRU\n{PIN.PIN_NUMBER} IS TURNED TO THIS BORE"

WALL_NOMINAL = (OD - BORE_DIA) / 2.0
WALL_WORST = (
    OD - printed_band_mm(OD_PLACES, unit=UNIT) - BORE_DIA - BORE_DIA_BAND[0]
) / 2.0
if WALL_WORST < WALL_TARGET_MM:
    raise AssertionError(f"MHA-PD-24 wall {WALL_WORST:.3f} under {WALL_TARGET_MM}")
# What the fit protects.  With the cluster forward the bushing is loose in
# the sleeve's end float and can cock on the pin as far as its bore lets it;
# cocked, it takes up its largest O.D. times that angle of the float.  At
# the modelled fit (clearance to .0025) that is .0049 of the .008 least
# float, so it never wedges between the arm's shims and the turning sleeve.
# Rule 4's own test: .002 looser (.0045) takes up .0088, more than the
# float (it goes whole at .0041), so the REAM answers the test itself and
# needs no exception; the next form down, a drilled #30 (.1285 +.004/0,
# clearance to .0080 on this pin), would take up .0157.
BORE_COCK_SPAN_MIN = (
    FIT.REAR_BUSHING_LENGTH
    - FIT.REAR_BUSHING_LENGTH_BAND
    - 2.0 * edge_break_chamfer_mm(unit=UNIT)
)


def bore_cock_take_up(clearance: float) -> float:
    """The end float the bushing takes up cocked at a diametral clearance."""
    return (OD + printed_band_mm(OD_PLACES, unit=UNIT)) * clearance / BORE_COCK_SPAN_MIN


BORE_COCK_TAKE_UP = bore_cock_take_up(FIT.BORE_DIAMETRAL_CLEARANCE[1])
if BORE_COCK_TAKE_UP >= FIT.RING_FLOAT_RANGE[0]:
    raise AssertionError(
        f"MHA-PD-24 cocked on the pin takes up {BORE_COCK_TAKE_UP:.4f} of the "
        f"sleeve's {FIT.RING_FLOAT_RANGE[0]} least end float"
    )

# --- Length: title block (owner ruling 2026-11-01, #2124) -----------------------
# The shims under it set the disc's end float, so its .XXX band only moves
# the shim count (transgear_cluster_fit.SHIM_COUNT_RANGE).
LENGTH = FIT.REAR_BUSHING_LENGTH  # .209
LENGTH_PLACES = FIT.LENGTH_PLACES
# Rule 4: the length names the stack it serves and where it is shimmed.
LENGTH_CALLOUT = f"{STACK_NAME},\nSHIMMED AT {STACK_SHEET}"

# The sleeve's rear face turns on the front face and thrusts on it, cluster
# rearward; the arm face only seats on the shims, at the title block's finish.
SLEEVE_NUMBER = _config.parts("pd-transgear-feed-pinion")["number"]
THRUST_FACE_CAPTION = f"THRUST FACE AGAINST\n{SLEEVE_NUMBER}"
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "sleeve_face",
        MACHINED_UM,
        PlanarFace((0.0, 0.0, 1.0), LENGTH),
        display_unit=UNIT,
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"RingOd", "BoreDia"},
    "Ring": {"RingLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"RingOd": OD_PLACES, "BoreDia": BORE_PLACES},
    "Ring": {"RingLength": LENGTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-PD-24 dimension needs authored places")
REFERENCE_DIMENSIONS: frozenset[str] = frozenset()

ISOMETRIC_VIEW_SCALE = (4, 1)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
