r"""Pure MHA-PD-28 transgear-knob-bush geometry shared by the bush, the arm
plate it is pressed in, the knob-shaft stack and the paper-drive assembly.

Owner ruling 2026-11-20 (Pedro), #2425: the MHA-PD-19 plate is a flat .197
plate, and the knob shaft's (MHA-PD-08) bearing is this turned, flanged
steel bush pressed into it.  The hub (Ø.52) stands in front of the plate's
face A and is the shoulder: its rear face seats on face A, its front face
(the hub face) is the MHA-PD-15 thrust ring's seat at the chain-plane station.
The press (Ø.4385 REF, turned to the plate's measured hole) runs from the
shoulder through the plate and on behind
it to the rear face, the MHA-PD-16 cup's thrust face.  The bore is drilled
.238 (letter B) with the turning and reamed .249 through after pressing, so
the press's closing-in never reaches the running fit.

Every nominal is the exact millimetre value of its printed inch value (#290).

Part frame (as MHA-PD-15/16): axis local +Y through the origin (``Axis1``);
the hub face is the Top Plane, y = 0; the shoulder face y = HUB_LENGTH; the
rear face y = LENGTH.  In the assembly the hub face stands HUB_LENGTH in
front of the plate's face A (machine z ``ARM_REAR - HUB_LENGTH``).

PURE DATA, no SolidWorks/COM calls.  It imports no plate, cup, shaft, ring
or registration module: they import it.
"""

from __future__ import annotations

import math

import _config
from _fit_ream_h7 import REAM_H7
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
)
from pd_cluster_stack_band import FIT_LENGTH_BAND_IN

UNIT = drawing_unit(
    "parts/pd-transgear-knob-bush", _config.parts("pd-transgear-knob-bush")
)

# --- Hub: the shoulder in front of face A -------------------------------------
# Ø.52, the MHA-PD-15 thrust ring's O.D. matches it (owner: "thrust ring
# diameter changed to match diameter of bush").  Nothing fits on it: .XX.
HUB_DIA = 13.208  # .52
HUB_DIA_PLACES = 2
# The hub face's station from the shoulder (face A): the plate's former
# .809 hub station (R9-25), the chain plane (contract §13) and the first term
# of the disc cluster's stack (F, transgear_cluster_fit), which sets the
# collar's air: .XXX at the cluster's ±.001 (#2124).
HUB_LENGTH = 20.5486  # .809
HUB_LENGTH_PLACES = 3
HUB_LENGTH_BAND = FIT_LENGTH_BAND_IN
# The press acceptance (registry process): a .002 feeler does not enter
# under the shoulder.  One-sided: the hub face may stand at most this much
# further forward of face A than HUB_LENGTH, never further back.  .002 is
# the coarsest leaf, in .001 steps, at which the MHA-PD-22 collar's air to
# the MHA-PD-06 disc still holds its floor (transgear_cluster_fit PS; .003
# leaves the statistical air 0.092 mm under its 0.1016); it was .0005, a
# check finer than .XXX with no failure to name (machinist review
# 20261124T013305458Z, rule 4; fit audit 2026-11-23, pending owner
# confirmation).
SHOULDER_SEAT_GAP_MAX = 0.0508  # .002

# --- Overall: hub face to rear face -------------------------------------------
# The knob's end float runs between the thrust ring on the hub face and the
# cup on the rear face, so this length sets the cup's station on the shaft
# (pd_transgear_knob_shaft_spec.CUP_FACE_STATION_BAND): the plate's former
# hub-to-boss length and band.
LENGTH = 29.0322  # 1.143
LENGTH_PLACES = 3
LENGTH_BAND = 0.0508  # ±.002, knob float
# Shoulder to rear face: the stub behind face A that the cup meets (REF).
STUB_LENGTH = LENGTH - HUB_LENGTH  # 8.4836, .334

# --- Press: made to the plate's reamed hole -----------------------------------
# Fit audit 2026-11-23 (pending owner confirmation; owner, 2026-11-23: "can
# the holes not be reamed in the first place"): MHA-PD-19's hole K is cut by
# the over/under set's .4385 reamer and prints that size with no band; this
# press step is turned LAST to the hole as measured, by the pilot-first
# method (a short pilot turned on the bar's end until the plate's hole just
# slides on it without shake, and miked; the pilot is then faced off and
# the step turned to that reading plus the interference), so no reamer,
# plug gauge or pin pair is bought for the hole.  The pilot only reads the
# hole: it is gone before the press diameter is cut, so the finished step
# is one diameter from the shoulder to the rear face, as the sheet draws it
# (traveler review r2: a pilot left on the bush was a land the drawing does
# not show).  The requirement is the interference, a range
# .0011 wide; the size prints REF.  What fails if it is loose: the press is
# the only thing that holds the knob axis K in the plate (no screw, pin or
# bond), and K sets the reducer mesh.
#
# The interference keeps ANSI B4.1-1967 force fit class FN2's limits for
# 0.40-0.56 in, 0.5-1.6 thousandths (verified 2026-11-20 against the table
# reprinted with ASME permission in R. L. Mott, Machine Elements in
# Mechanical Design 4th ed., Table 13-4;
# https://users.encs.concordia.ca/~nrskumar/Index_files/Mech344/Table-Force_and_Shrink_Fits.pdf).
# Both diameters are modelled line to line at the reamer's Ø.4385, as the
# repo's other presses are.
PRESS_DIA = 11.1379  # .4385 REF
PRESS_DIA_PLACES = 4
# (least, greatest) diametral interference to the measured hole: the
# requirement the sheet prints.
PRESS_INTERFERENCE = (0.0127, 0.04064)  # .0005-.0016
# ANALYSIS bands, not printed limits, (upper, lower): what the set reamer is
# modelled to cut in MHA-PD-19 (REAM_H7, +.0005/0), and the press diameters
# that fit gives over that range of holes, for the walls and the envelope.
PRESS_HOLE_BAND = REAM_H7
PRESS_DIA_BAND = (
    round(max(PRESS_HOLE_BAND) + PRESS_INTERFERENCE[1], 6),
    round(min(PRESS_HOLE_BAND) + PRESS_INTERFERENCE[0], 6),
)  # +.0021/+.0005, .4390/.4406
if PRESS_INTERFERENCE[1] - PRESS_INTERFERENCE[0] < 0.0254 - 1e-9:
    raise AssertionError("MHA-PD-28's interference range is narrower than .001")
# The smallest finished press diameter (ANALYSIS): the least interference
# over the smallest hole the reamer is modelled to cut.
PRESS_DIA_MIN = PRESS_DIA + min(PRESS_DIA_BAND)  # .4390

# --- Bore: reamed through after pressing --------------------------------------
# The .2490 chucking reamer's size (#290 fit D8; reamer-2490, to order: not
# on hand) under the knob shaft's journal, which is turned to this bore: the
# plate's former running bore.  The sheet prints the reamer's size and no
# band (drawing-guidelines rule 4; fit audit 2026-11-23, pending owner
# confirmation).  BORE_DIA_LIMITS is the ANALYSIS band, what the reamer is
# taken to cut, for the wall and the tilt stacks: the modelled result, not
# printed limits.  A fit .002 looser trebles the journal's shake in the
# bore, which the reducer mesh's backlash and the collar air's tilt term
# (pd_cluster_air) both pay.
BORE_DIA = 6.3246  # .249
BORE_DIA_LIMITS = (min(REAM_H7), max(REAM_H7))  # analysis: +.0000/+.0005
BORE_PLACES = 4
# Letter B, drilled with the turning: the reamer's stock after the press has
# closed the hole in.  The drill never cuts to the reamed size.
PRE_REAM_DRILL_DIA = 6.0452  # .238
if PRE_REAM_DRILL_DIA + drilled_oversize_mm(unit=UNIT) >= BORE_DIA + min(
    BORE_DIA_LIMITS
):
    raise AssertionError("MHA-PD-28's B drill leaves the reamer nothing to cut")

# --- Edge breaks and the bore's shortest cylinder -----------------------------
# The inch title block's edge-break row: either permitted form, the round or
# the chamfer, takes its full size off the bore's mouths.
EDGE_BREAK_MAX_MM = max(
    edge_break_radius_mm(unit=UNIT), edge_break_chamfer_mm(unit=UNIT)
)
# The bore's shortest full cylinder: the length at its lower limit less the
# break at both mouths (the perpendicularity frame's feature length).
KNOB_BORE_LENGTH_MIN_MM = LENGTH - LENGTH_BAND - 2.0 * EDGE_BREAK_MAX_MM

# --- Shoulder root and the plate hole's mouth -----------------------------------
# The title block lets an inside corner run to R.040, which would ride the
# press hole's mouth and hold the shoulder off face A, so the root carries
# its own smaller limit as a native fillet (title_block.yaml, #1625/#1636),
# printed R.005 MAX.  MHA-PD-19's hole mouth at face A carries a .015 x 45°
# chamfer (#2425, the press's lead-in; the plate reads it here as it reads
# PRESS_HOLE_BAND), its printed .XXX leg never under the root, so the
# shoulder seats.
SHOULDER_ROOT_R_MAX_MM = 0.127  # .005 MAX
SHOULDER_ROOT_R_PLACES = 3
PRESS_HOLE_MOUTH_CHAMFER = 0.381  # .015 x 45°, on MHA-PD-19
PRESS_HOLE_MOUTH_CHAMFER_PLACES = 3
_MOUTH_BAND = printed_band_mm(PRESS_HOLE_MOUTH_CHAMFER_PLACES, unit=UNIT)
PRESS_HOLE_MOUTH_CHAMFER_MIN = PRESS_HOLE_MOUTH_CHAMFER - _MOUTH_BAND
PRESS_HOLE_MOUTH_CHAMFER_MAX = PRESS_HOLE_MOUTH_CHAMFER + _MOUTH_BAND
# A 45° chamfer of leg c clears every point of a root fillet of radius r
# (each lies within x + y <= r of the corner) once c >= r.
if PRESS_HOLE_MOUTH_CHAMFER_MIN < SHOULDER_ROOT_R_MAX_MM - 1e-9:
    raise AssertionError("MHA-PD-28's shoulder root rides MHA-PD-19's hole mouth")

# --- Walls at the printed worst case (drawing-guidelines.md rule 17) ----------
# The hub and the press are turned with the B drill in one chucking, and the
# final ream after pressing is a separate setup that follows that drilled
# hole, so each wall pays the repo's 0.3 deg drill run-off (#2000 holds the
# method) over the bore's longest length, and the title block's break on
# both rims of its end face (the old plate hub's and boss's convention).
DRILL_RUN_OFF_DEG = 0.3
BORE_RUN_OFF_MM = (LENGTH + LENGTH_BAND) * math.tan(math.radians(DRILL_RUN_OFF_DEG))
_BORE_R_MAX = (BORE_DIA + max(BORE_DIA_LIMITS)) / 2.0
_HUB_DIA_MIN = HUB_DIA - printed_band_mm(HUB_DIA_PLACES, unit=UNIT)
_PRESS_DIA_MIN = PRESS_DIA_MIN
_PRESS_HOLE_MAX = PRESS_DIA + PRESS_HOLE_BAND[0]
WALLS: dict[str, tuple[float, float]] = {  # (nominal, worst)
    "press section over the bore": (
        (PRESS_DIA - BORE_DIA) / 2.0,
        _PRESS_DIA_MIN / 2.0 - _BORE_R_MAX - BORE_RUN_OFF_MM - 2.0 * EDGE_BREAK_MAX_MM,
    ),
    "hub over the bore": (
        (HUB_DIA - BORE_DIA) / 2.0,
        _HUB_DIA_MIN / 2.0 - _BORE_R_MAX - BORE_RUN_OFF_MM - 2.0 * EDGE_BREAK_MAX_MM,
    ),
}
WALL_FLOOR = WALL_FLOOR_MM
WALL_TARGET = WALL_TARGET_MM
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_FLOOR:
        raise AssertionError(
            f"MHA-PD-28 {_name} wall {_worst:.4f} at the printed worst case is "
            f"under the {WALL_FLOOR} floor"
        )
WALL_WORST = min(worst for _nominal, worst in WALLS.values())  # the press, .0688
# Rule 20: under the target, the sheet states the wall as a plain fact,
# floored to three places so it never claims more than is left.
WALL_STATED_MIN = math.floor(WALL_WORST / 25.4 * 1000.0 + 1e-9) / 1000.0 * 25.4
# Informational, not a rule-17 wall: the shoulder's flat radial land on
# face A, the smallest hub over the largest press hole, less the hole
# mouth's largest chamfer leg and the break on the hub's rim.
SHOULDER_LAND_WORST = (
    (_HUB_DIA_MIN - _PRESS_HOLE_MAX) / 2.0
    - PRESS_HOLE_MOUTH_CHAMFER_MAX
    - EDGE_BREAK_MAX_MM
)
if SHOULDER_LAND_WORST <= 0.0:
    raise AssertionError("MHA-PD-28's shoulder keeps no flat land on face A")
