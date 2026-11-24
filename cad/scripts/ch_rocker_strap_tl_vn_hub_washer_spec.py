r"""MHA-CH-13-TL-VN-52, the rocker strap fixture's hub washer: McMaster 96659A104.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure. Shop fixture hardware (cad/docs/subsystem-identities.md) for the
rocker-strap sub-plate fixture MHA-CH-13-TL-00: the #10 SAE flat washer
under the #10-32 hub screw's head (MHA-CH-13-TL-VN-51), bearing on the strap
blank's top round its reamed hub hole while the outline is cut. One washer
picked by measurement from the owned pack of 100 (PO 1103PCAMPOS, bought as
MHA-SM-VN-54) and kept with the fixture.

Owner rulings 2026-11-23 (Pedro). Option A: "change the screw to #10-32. The
sub-plate's tapped hole becomes #10-32 and the plug's bore .201 (#7 drill).
The washer is then a #10 SAE washer you already own (McMaster 96659A104,
.219 x .500, pack of 100 from PO 1103PCAMPOS), used as supplied. The made
washer, its drawing and its lathe traveler are deleted." (It reverses
2026-11-17's "Use a 1/4-20 hub screw", under which the washer was the turned
MHA-CH-13-TL-03, retired.) On the washer's reach: "Pick one washer from the
pack of 100 by measurement and keep it with the fixture: OD .505 or under
and bore .220 or under (limits to be confirmed by the agent so the 0.5 mm
clearance holds even pushed to one side). The traveler says to mike it once
and centre it by eye. Nothing to buy but the #10-32 screw."

Catalogue (``_mcmaster_96659a104``, read live again 2026-11-23): 18-8
stainless SAE washer for a No. 10 screw, ID .219, OD .500, thickness .036 to
.065, ASME B18.21.1 (Table 11: ID .214-.227, OD .495-.515; section 4.5's
OD-to-ID runout .013, taken as a full radial offset). The recipe is the
shared ``diagnostics/diag_build_96659A104.py`` (catalog-only), modelled at
the nominal diameters and the thickness range's mid value.

The selection limits and what they hold. The washer lies loose on the screw,
so its rim can reach, from the strap programs' hub centre, half its OD plus
its bore's play on the smallest screw (the class 3A major's minimum) plus its
OD-to-ID runout plus the tapped hole's own position error. At OD .505 and
bore .220, with the runout at the standard's whole .013 (no third
measurement): centred it keeps the plan's 0.5 mm from the cutter; pushed
fully to one side it reaches 7.273 mm, inside the radius the outline program
guards (bushing_flange_dia_mm / 2 + bushing_clearance_mm, which cam.py
refuses a cutter edge inside) but only 0.22 mm from the cutter's nearest
edge (7.49 mm), not 0.5: no washer in the standard's band keeps 0.5 mm
pushed aside (it would need OD .472; the minimum is .495). Owner ruling
2026-11-24 (Pedro), on that shortfall: "Accept as is: centre the washer by
eye, 0.5 mm centred, 0.22 mm worst case; the traveler says to centre it and
to watch the first level." It still covers the hub hole all round.

Part frame: the recipe's +Y axis turned onto +Z; z = 0 the face on the
strap, the face under the screw head at z = THICKNESS; the axis published
as ``ScrewAxis`` (Top ∩ Right).

Mirrored constants: the strap's hub hole, the plan's keep-out and the
plate's hub position band are copied, not imported (the strap spec pulls the
rocker-arm spec into this closure, the plate spec would re-key the washer on
every plate edit, and no COM leaf may read a plan TOML);
``test_ch_rocker_strap_tl_vn_hub_washer_hardware`` asserts each copy.
"""

from __future__ import annotations

import math

import _config
import _mcmaster_91255a267 as screw
from _mcmaster_96659a104 import DIMS

PART_NAME = "ch-rocker-strap-tl-vn-hub-washer"
_ROW = _config.parts("ch-rocker-strap-tl-vn-hub-washer")
PART_NUMBER = str(_ROW["number"])
SKU = DIMS.part_no
QUANTITY = 1
if int(_ROW["quantity"]) != QUANTITY:
    raise AssertionError(f"{SKU}: one washer under the hub screw")
INCH = 25.4

# --- The modelled washer (catalogue nominals, mid thickness) -------------------
OUTER_DIA = DIMS.od
BORE_DIA = DIMS.id
THICKNESS = DIMS.thickness
THICKNESS_MAX = DIMS.thickness_max
THICKNESS_MIN = DIMS.thickness_min

# --- The selection (owner ruling 2026-11-23) -----------------------------------
# Measured once, before the first blank: OD by micrometer, bore by pin
# gauges. The lower ends are the standard's.
SELECT_OD_MAX = 0.505 * INCH  # 12.827
SELECT_BORE_MAX = 0.220 * INCH  # 5.588
SELECT_OD_MIN = DIMS.od_min  # .495
SELECT_BORE_MIN = DIMS.id_min  # .214
if not SELECT_OD_MIN < SELECT_OD_MAX <= DIMS.od_max:
    raise AssertionError("the OD selection limit is outside the standard's band")
if not SELECT_BORE_MIN < SELECT_BORE_MAX <= DIMS.id_max:
    raise AssertionError("the bore selection limit is outside the standard's band")
if not SELECT_BORE_MIN > screw.MAJOR_DIA:
    raise AssertionError("the smallest washer bore does not pass the #10 screw")

# --- Mirrored mates (asserted against their authorities in the pytest) ---------
# The strap plan's hub keep-out: bushing_flange_dia_mm, bushing_clearance_mm
# and bushing_stack_height_mm.
PLAN_FLANGE_DIA = 13.716
PLAN_CLEARANCE = 0.5
PLAN_STACK_HEIGHT = 5.1308
KEEP_RADIUS = PLAN_FLANGE_DIA / 2.0 + PLAN_CLEARANCE  # 7.358
# MHA-CH-13's reamed hub hole, .400 +.0005/.0000, at its largest.
STRAP_HOLE_DIA_MAX = 10.1727
# MHA-CH-13-TL-01: the hub hole's position from X0 and Y0, +/-.002 each way.
HUB_LOCATION_TOL = 0.0508
# MHA-CH-13-TL-02: the most its play lets the hub hole sit off the
# counterbore (HUB_LOCATING_ERROR_MAX).
PLUG_LOCATING_ERROR_MAX = 0.04445

# --- Reach: the selected washer pushed fully to one side -----------------------
# Its bore against the smallest screw; its OD off its bore by the standard's
# whole runout; the tapped hole off the programs' hub centre by its position
# band on both axes. The screw's own play in the tapped thread is not added:
# snugged, the thread's flanks centre it.
RADIAL_PLAY_MAX = (SELECT_BORE_MAX - screw.MAJOR_DIA_MIN) / 2.0  # 0.4572
RUNOUT_MAX = DIMS.od_id_runout_max  # 0.3302
SCREW_AXIS_ERROR_MAX = HUB_LOCATION_TOL * math.sqrt(2.0)  # 0.0718
REACH_CENTRED_MAX = SELECT_OD_MAX / 2.0 + RUNOUT_MAX + SCREW_AXIS_ERROR_MAX
REACH_MAX = REACH_CENTRED_MAX + RADIAL_PLAY_MAX  # 7.273
if not REACH_MAX <= KEEP_RADIUS:
    raise AssertionError(
        f"the selected washer can reach {REACH_MAX:.3f} mm from the hub centre, "
        f"past the {KEEP_RADIUS:.3f} mm the outline program keeps its cutter out of"
    )
# Owner ruling 2026-11-24 (Pedro): "Accept as is: centre the washer by eye,
# 0.5 mm centred, 0.22 mm worst case; the traveler says to centre it and to
# watch the first level." The worst case is the washer pushed fully aside
# against the outline cutter's nearest edge to the hub centre (the strap's
# bottom edge, 7.49 mm: the strap plan's bushing_* comment).
# The plan's 0.5 mm is held centred (below), not pushed aside.
CUTTER_EDGE_MIN = 7.49
ACCEPTED_WORST_CLEARANCE = 0.22
WORST_CLEARANCE = CUTTER_EDGE_MIN - REACH_MAX  # 0.217
if not WORST_CLEARANCE >= ACCEPTED_WORST_CLEARANCE - 0.005:
    raise AssertionError(
        f"pushed fully aside the washer is {WORST_CLEARANCE:.3f} mm from the "
        f"cutter, under the {ACCEPTED_WORST_CLEARANCE} mm the owner accepted"
    )
# Centred by eye (its bore's play taken up evenly) its rim stays inside the
# plan's flange diameter, so the cutter passes the plan's whole clearance off.
if not REACH_CENTRED_MAX <= PLAN_FLANGE_DIA / 2.0 + 1e-9:
    # 6.4135 + 0.3302 + 0.0718 = 6.8155 <= 6.858
    raise AssertionError("centred, the selected washer breaks the plan's flange")

# --- Land: it bears on the strap round the hub hole ----------------------------
# Thin side, the smallest washer pushed fully to one side: half the OD less
# the play, the runout, the tapped hole's offset from the counterbore and
# the plug's locating error, measured from the largest hub hole's edge.
BEARING_LAND_CENTRED_MIN = (SELECT_OD_MIN - STRAP_HOLE_DIA_MAX) / 2.0  # 1.200
BEARING_LAND_MIN = (
    BEARING_LAND_CENTRED_MIN
    - RADIAL_PLAY_MAX
    - RUNOUT_MAX
    - SCREW_AXIS_ERROR_MAX
    - PLUG_LOCATING_ERROR_MAX
)  # 0.297
if not BEARING_LAND_CENTRED_MIN > 1.0:
    raise AssertionError("the washer leaves no land on the strap round its hub hole")
if not BEARING_LAND_MIN > 0.25:
    raise AssertionError(
        "pushed to one side the washer no longer covers the hub hole all round"
    )
if not SELECT_BORE_MAX < STRAP_HOLE_DIA_MAX:
    raise AssertionError("the washer bore is larger than the hub hole it covers")
# The smallest head still bears on the washer all round its bore.
HEAD_LAND_MIN = (screw.HEAD_DIA_MIN - SELECT_BORE_MAX) / 2.0 - RADIAL_PLAY_MAX
if not HEAD_LAND_MIN > 0.5:
    raise AssertionError("the screw head can drop into the washer's bore")

# --- Stack: the thickest washer under the tallest head -------------------------
STACK_HEIGHT_MAX = THICKNESS_MAX + screw.HEAD_HEIGHT  # 4.216, .166
if not STACK_HEIGHT_MAX <= PLAN_STACK_HEIGHT:
    raise AssertionError("washer and screw head break the plan's hub stack height")
if not screw.HEAD_DIA < SELECT_OD_MIN:
    raise AssertionError("the screw head overhangs the washer")


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text, no leading zero."""
    return f"{value_mm / INCH:.{places}f}".removeprefix("0")


SELECT_OD_TEXT = inch_text(SELECT_OD_MAX, 3)
SELECT_BORE_TEXT = inch_text(SELECT_BORE_MAX, 3)


def washer_volume() -> float:
    """Nominal annulus volume of the modelled washer, in mm^3."""
    return math.pi / 4 * (OUTER_DIA**2 - BORE_DIA**2) * THICKNESS
