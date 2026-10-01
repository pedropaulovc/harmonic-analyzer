r"""MHA-127 latch-hook: printed dimensions, bands, walls and sheet notes.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Geometry is ``latch_hook_geometry``'s; this module decides what the
sheet prints, at how many places, and proves the walls at the worst case of
those printed bands.

Process: 10 x 0.6 dead-soft bright low-carbon strip (not hardened spring
steel, so the 0.76 % edgewise set holds; in service it flexes elastically,
about 0.1 %), bent edgewise over a template of the inner edge, the top end cut
square, the free end rounded, then the three holes drilled.  The width and
thickness are the stock's and print as a reference.

Datums the sheet uses: the square top cut (every run along the strip is taken
from it) and the strip's own width (the pin hole, and the rivet pair's
midpoint, are centred across it).

Bands (title block unless stated):

* the template -- inner-edge radii, the tangency run, the tip run -- at .X;
* the pin hole's run at .XX: the hook is set at assembly with the 1/8 pin
  entering the Ø5.4 without touching, and the flap drilled through it after
  (R9-15), so the set takes up the run's band.  The pin crosses the strip
  obliquely and sweeps a 4.16 long footprint along it, which leaves 0.62
  each side at that pose (R9-24).  The MHA-170 flap's walls hold 2.0 over
  that set range only (``latch_hook_bracket_spec.HOOK_SET_RANGE``): the .X
  row's 0.8 would leave its upper rivet hole 1.79 from the flap's top;
* the rivet pair's run and pitch at .XXX: two Ø1.65 holes across a 10 strip
  hold the 2.0 web and edge walls only at that band.  The MHA-170 flap's
  holes are drilled through these at assembly, so nothing else registers on
  them;
* the pin hole's and the rivet pair's midpoint's centring across the width
  within ``CENTRING_BAND`` (a note): the Ø5.4 pin hole (sized over the pin)
  leaves 2.3 each side in the 10 strip, so centring is the whole margin.

The inner edge the template carries is fully defined by the sheet: R845.0
centred on the top cut's line (it leaves the cut square), R485.0 tangent to
it at the 52.9 run, both centres on the inner side.
"""

from __future__ import annotations

import math

from _printed_tolerance import drilled_oversize_mm, printed_deviations
from latch_hook_bracket_geometry import BAR_CENTRE_Y
from latch_hook_geometry import (
    HALF_W,
    INNER_R1,
    INNER_R2,
    JUNCTION_RUN,
    PIN_HOLE_CENTRELINE_OFFSET,
    PIN_HOLE_DIA,
    PIN_HOLE_YZ,
    PLANE_X,
    RIVET_HOLE_DIA,
    RIVET_PITCH,
    RIVET_RUN,
    STRIP_T,
    STRIP_W,
    TIP_R,
    TIP_RUN,
)
from support_bar_spec import HANGER_TAP_Y, PIVOT_TAP_X
from transgear_latch_pin_spec import DIA_MAX as PIN_DIA_MAX

WALL_TARGET = 2.0
WALL_FLOOR = 1.5

# Supplied strip: width ±0.1 (each edge ±0.05 about the centre the holes are
# centred on); thickness as supplied.
STOCK_WIDTH_TOL = 0.1
CENTRING_BAND = 0.06  # hole centre to the strip's mid-width, each way
# The pin hole is modelled on the pin's axis, off the centreline by the arm's
# pin height (R9-26); the printed centring band must cover that.
if abs(PIN_HOLE_CENTRELINE_OFFSET) > CENTRING_BAND:
    raise AssertionError(
        f"MHA-127 pin hole sits {PIN_HOLE_CENTRELINE_OFFSET:.3f} off the strip"
        f" centreline, outside the {CENTRING_BAND} centring band"
    )
# Drilled holes: +0.10/0 (title block DRILLED HOLES row).
HOLE_BAND = (drilled_oversize_mm(), 0.0)  # (upper, lower) deviations

# Places each printed dimension carries.
TEMPLATE_PLACES = 1
PIN_RUN_PLACES = 2
RIVET_PLACES = 3
HOLE_DIA_PLACES = 2

# The 1/8 latch pin's footprint on the strip.  At the fit-up pose the pin's
# axis runs on the arm's centreline from the pivot P through the hole's
# centre on the strip's mid-plane, in a plane of constant z; the strip's
# faces are normal to machine X, so the pin crosses them at PIN_INCIDENCE
# and its full diameter sweeps D / cos + T tan along the trace.
_PIVOT_XY = (PIVOT_TAP_X, BAR_CENTRE_Y + HANGER_TAP_Y)
_HOLE_XY = ((PLANE_X[0] + PLANE_X[1]) / 2.0, PIN_HOLE_YZ[0])
PIN_INCIDENCE = math.atan2(
    abs(_HOLE_XY[1] - _PIVOT_XY[1]), _HOLE_XY[0] - _PIVOT_XY[0]
)  # 32.56 deg
PIN_FOOTPRINT_ALONG = PIN_DIA_MAX / math.cos(PIN_INCIDENCE) + STRIP_T * math.tan(
    PIN_INCIDENCE
)  # 3.776 + 0.383 = 4.159
# The least pin-to-hole clearance the latch keeps.
PIN_CLEARANCE_MIN = 0.28


def _lo(model: float, places: int) -> float:
    return printed_deviations(model, places)[0]


def _hi(model: float, places: int) -> float:
    return printed_deviations(model, places)[1]


_HOLE_OVER = max(HOLE_BAND)

# --- Walls at the printed worst case -------------------------------------------
# Rivet holes to the square top cut: run printed from that edge.
RIVET_TOP_WALL = RIVET_RUN - (RIVET_HOLE_DIA + _HOLE_OVER) / 2.0
RIVET_TOP_WALL_WORST = RIVET_TOP_WALL + _lo(RIVET_RUN, RIVET_PLACES)
# Rivet holes to the long edges: half the pitch outward (pitch at its upper
# limit), the pair off-centre by the centring band, the narrowest stock.
RIVET_EDGE_WALL = HALF_W - RIVET_PITCH / 2.0 - (RIVET_HOLE_DIA + _HOLE_OVER) / 2.0
RIVET_EDGE_WALL_WORST = (
    RIVET_EDGE_WALL
    - _hi(RIVET_PITCH, RIVET_PLACES) / 2.0
    - CENTRING_BAND
    - STOCK_WIDTH_TOL / 2.0
)
# The web between the two rivet holes, pitch at its lower limit.
RIVET_WEB = RIVET_PITCH - (RIVET_HOLE_DIA + _HOLE_OVER)
RIVET_WEB_WORST = RIVET_WEB + _lo(RIVET_PITCH, RIVET_PLACES)
# The pin hole to the long edges.
PIN_LIGAMENT = HALF_W - (PIN_HOLE_DIA + _HOLE_OVER) / 2.0
PIN_LIGAMENT_WORST = PIN_LIGAMENT - CENTRING_BAND - STOCK_WIDTH_TOL / 2.0

WALLS_WORST = {
    "rivet hole to top cut": RIVET_TOP_WALL_WORST,
    "rivet hole to long edge": RIVET_EDGE_WALL_WORST,
    "rivet web": RIVET_WEB_WORST,
    "pin hole to long edge": PIN_LIGAMENT_WORST,
}
for _name, _wall in WALLS_WORST.items():
    if _wall < WALL_TARGET - 1e-9:
        raise AssertionError(
            f"MHA-127 {_name} {_wall:.3f} at the printed worst case is under "
            f"the {WALL_TARGET} target"
        )

# --- The latch pin enters the Ø5.4 at the fit-up pose --------------------------
# The hook is set on the pin before the flap is drilled through its rivet
# holes (R9-15), so the set takes up the run's band, as it does the rivet
# holes' misalignment: the clearance is the hole's least size about the
# swept footprint.
PIN_CLEARANCE_ALONG = (PIN_HOLE_DIA - PIN_FOOTPRINT_ALONG) / 2.0  # 0.620
if PIN_CLEARANCE_ALONG < PIN_CLEARANCE_MIN - 1e-9:
    raise AssertionError(
        f"MHA-127 pin hole leaves {PIN_CLEARANCE_ALONG:.3f} pin clearance at the"
        f" fit-up pose, under {PIN_CLEARANCE_MIN}"
    )

# --- Sheet ---------------------------------------------------------------------
PIN_HOLE_CALLOUT = "DRILL THRU"
RIVET_HOLE_CALLOUT = "2X DRILL THRU"
# The template's construction, under its imported dimensions: R845.0 leaves
# the square top cut with its centre on the cut's line (the model's "arc 1
# centre under the top cut"), R485.0 is tangent to it at the 52.9 run.
INNER_R1_CALLOUT = "CENTRE ON TOP CUT\nLINE EXTENDED"
INNER_R2_CALLOUT = "TANGENT TO\nADJOINING ARC"
JUNCTION_RUN_CALLOUT = "TO TANGENT POINT"
# TipRun ends at the full round's centre; the overall to its extreme prints
# as a reference beside it.
TIP_RUN_CALLOUT = "TO FULL-ROUND CENTRE"
OVERALL_LENGTH = TIP_RUN + TIP_R
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    "overall length reference": TEMPLATE_PLACES
}
# The title block's MATERIAL cell prints the registry row's ``material`` (the
# stock, so no note restates it; width and thickness are the strip's).
MATERIAL_TITLE = f"Dead-soft steel strip {STRIP_W:g} x {STRIP_T:g}"

DRAWING_NOTES = "\n".join(
    (
        "1. BEND EDGEWISE OVER A TEMPLATE OF THE INNER EDGE; STRIP TO LIE FLAT.",
        "2. CUT TOP END SQUARE; FULL-ROUND FREE END; DRILL HOLES AFTER BENDING.",
        "3. CENTRE PIN HOLE AND 2X RIVET HOLES' MIDPOINT ON WIDTH WITHIN "
        f"{CENTRING_BAND:.2f}.",
        "4. AT ASSEMBLY: SET ON MHA-169 PIN CLEAR; DRILL MHA-170 FLAP THRU 2X.",
    )
)

# Marked model dimensions and the places the model authors on them.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HookProfile": {"InnerR1", "InnerR2", "JunctionRun", "TipRun"},
    "PinHoleProfile": {"PinHoleRun", "PinHoleDia"},
    "RivetHoleProfile": {"RivetRun", "RivetPitch", "RivetHoleDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HookProfile": {
        "InnerR1": TEMPLATE_PLACES,
        "InnerR2": TEMPLATE_PLACES,
        "JunctionRun": TEMPLATE_PLACES,
        "TipRun": TEMPLATE_PLACES,
    },
    "PinHoleProfile": {"PinHoleRun": PIN_RUN_PLACES, "PinHoleDia": HOLE_DIA_PLACES},
    "RivetHoleProfile": {
        "RivetRun": RIVET_PLACES,
        "RivetPitch": RIVET_PLACES,
        "RivetHoleDia": HOLE_DIA_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# Model values of the printed template dimensions (for the sheet's checks).
TEMPLATE_VALUES = {
    "InnerR1": INNER_R1,
    "InnerR2": INNER_R2,
    "JunctionRun": JUNCTION_RUN,
    "TipRun": TIP_RUN,
}
