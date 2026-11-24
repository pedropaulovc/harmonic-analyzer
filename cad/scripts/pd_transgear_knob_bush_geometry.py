r"""Pure MHA-PD-28 transgear-knob-bush geometry shared by the bush, the arm
plate it is bonded in, the knob-shaft stack and the paper-drive assembly.

Owner ruling 2026-11-20 (Pedro), #2425: the MHA-PD-19 plate is a flat .197
plate, and the knob shaft's (MHA-PD-08) bearing is this turned, flanged
steel bush fixed in it.  The hub (Ø.52) stands in front of the plate's
face A and is the shoulder: its rear face seats on face A, its front face
(the hub face) is the MHA-PD-15 thrust ring's seat at the chain-plane station.
The stub (Ø.4370 ±.0010) runs from the shoulder through the plate's .4385
reamed hole and on behind it to the rear face, the MHA-PD-16 cup's thrust
face; it is bonded in the hole with LOCTITE 638 (owner question Q8b,
option B, held for the owner; it was a
press turned to the measured hole).  The bore is drilled .238 (letter B)
with the turning and reamed .249 through after the bond has cured.

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
# The seat acceptance (registry process): a .002 feeler does not enter
# under the shoulder.  One-sided: the hub face may stand at most this much
# further forward of face A than HUB_LENGTH, never further back.  .002 is
# the coarsest leaf, in .001 steps, at which the MHA-PD-22 collar's air to
# the MHA-PD-06 disc still holds its floor (transgear_cluster_fit PS; .003
# leaves the statistical air 0.092 mm under its 0.1016); it was .0005, a
# check finer than .XXX with no failure to name (machinist review
# 20261124T013305458Z; rule 4's necessity test, MHA-PD-00 register N-16:
# fit audit question 5 added collar air, so whether .002 is still needed
# is open in #3528).
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

# --- Stub: bonded in the plate's reamed hole ----------------------------------
# Owner question Q8b, held for the owner (option B,
# the lane's recommendation B; the fit policy the owner approved on
# 2026-11-24 calls a press over-specified where a bond would hold): the stub
# is a slip fit bonded with LOCTITE 638 in MHA-PD-19's hole K, which keeps
# the over/under set's .4385 reamer and prints that size with no band, so
# the plate's walls stand.  It replaces the press turned to the hole as
# measured (the pilot reading in tenths and the arbor press).  The stub
# prints the shop's turned-diameter row, ±.001, about the size that gives
# the bond's clearance over every hole the reamer is modelled to cut:
# .0005-.0030, inside the 638 gap limit.  What fails if it is loose past
# that: the bond is what holds the knob axis K in the plate (no screw or
# pin), and K sets the reducer mesh; the plate is located on the arm at
# DETAIL K (MHA-PD-00 step 12) only after the bush is bonded, so the stub's
# float in its gap is taken out there.
PRESS_HOLE_DIA = 11.1379  # .4385, MHA-PD-19's hole K (its reamer's size)
# ANALYSIS band (upper, lower), not printed limits: what the set reamer is
# modelled to cut in MHA-PD-19 (REAM_H7, +.0005/0).
PRESS_HOLE_BAND = REAM_H7
STUB_DIA = 11.0998  # .4370
STUB_DIA_PLACES = 4
STUB_DIA_TOLERANCE = 0.0254  # ±.001, the shop's turned-diameter row
STUB_DIA_MIN = STUB_DIA - STUB_DIA_TOLERANCE  # .4360
STUB_DIA_MAX = STUB_DIA + STUB_DIA_TOLERANCE  # .4380
# LOCTITE 638's TDS gap fill, the limit the repo's other 638 joints hold
# (pd_transgear_pin_spec, pd_transgear_pivot_spacer_spec,
# sm_gooseneck_spring_joint; test_pd_transgear_knob_bush_drawing pins it).
LOCTITE_638_GAP_MAX = 0.25
# (least, greatest) diametral clearance: the largest stub in the smallest
# hole, and the reverse.  The sheet prints it beside the stub.
BOND_CLEARANCE = (
    round(PRESS_HOLE_DIA + min(PRESS_HOLE_BAND) - STUB_DIA_MAX, 6),
    round(PRESS_HOLE_DIA + max(PRESS_HOLE_BAND) - STUB_DIA_MIN, 6),
)  # .0005, .0030
if not 0.0 < BOND_CLEARANCE[0] <= BOND_CLEARANCE[1] <= LOCTITE_638_GAP_MAX:
    raise AssertionError(
        f"MHA-PD-28's bond clearance {BOND_CLEARANCE} is not a slip fit inside "
        "LOCTITE 638's gap limit"
    )
# The stub may cure off the hole's axis by half the greatest clearance.
SEAT_OFFSET_MAX = BOND_CLEARANCE[1] / 2.0  # .0015

# --- Bore: reamed through after the bond has cured ----------------------------
# The .2490 chucking reamer's size (#290 fit D8; reamer-2490, to order: not
# on hand) under the knob shaft's journal, which is turned to this bore: the
# plate's former running bore.  The sheet prints the reamer's size and no
# band (drawing-guidelines rule 4, form 2).  BORE_DIA_LIMITS is the
# ANALYSIS band, what the reamer is
# taken to cut, for the wall and the tilt stacks: the modelled result, not
# printed limits.  A fit .002 looser trebles the journal's shake in the
# bore, which the reducer mesh's backlash and the collar air's tilt term
# (pd_cluster_air) both pay.
BORE_DIA = 6.3246  # .249
BORE_DIA_LIMITS = (min(REAM_H7), max(REAM_H7))  # analysis: +.0000/+.0005
BORE_PLACES = 4
# Letter B, drilled with the turning: the reamer's stock, reamed in place
# once the bush is bonded.  The drill never cuts to the reamed size.
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
# hole's mouth and hold the shoulder off face A, so the root carries
# its own smaller limit as a native fillet (title_block.yaml, #1625/#1636),
# printed R.005 MAX.  MHA-PD-19's hole mouth at face A carries a .015 x 45°
# chamfer (#2425, the stub's lead-in; the plate reads it here as it reads
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
# The hub and the stub are turned with the B drill in one chucking, and the
# final ream after bonding is a separate setup that follows that drilled
# hole, so each wall pays the repo's 0.3 deg drill run-off (#2000 holds the
# method) over the bore's longest length, and the title block's break on
# both rims of its end face (the old plate hub's and boss's convention).
DRILL_RUN_OFF_DEG = 0.3
BORE_RUN_OFF_MM = (LENGTH + LENGTH_BAND) * math.tan(math.radians(DRILL_RUN_OFF_DEG))
_BORE_R_MAX = (BORE_DIA + max(BORE_DIA_LIMITS)) / 2.0
_HUB_DIA_MIN = HUB_DIA - printed_band_mm(HUB_DIA_PLACES, unit=UNIT)
_PRESS_HOLE_MAX = PRESS_HOLE_DIA + max(PRESS_HOLE_BAND)
WALLS: dict[str, tuple[float, float]] = {  # (nominal, worst)
    "stub section over the bore": (
        (STUB_DIA - BORE_DIA) / 2.0,
        STUB_DIA_MIN / 2.0 - _BORE_R_MAX - BORE_RUN_OFF_MM - 2.0 * EDGE_BREAK_MAX_MM,
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
WALL_WORST = min(worst for _nominal, worst in WALLS.values())  # the stub, .0673
# Rule 20: under the target, the sheet states the wall as a plain fact,
# floored to three places so it never claims more than is left.
WALL_STATED_MIN = math.floor(WALL_WORST / 25.4 * 1000.0 + 1e-9) / 1000.0 * 25.4
# Informational, not a rule-17 wall: the shoulder's flat radial land on
# face A, the smallest hub over the largest hole, less the hole
# mouth's largest chamfer leg and the break on the hub's rim.
SHOULDER_LAND_WORST = (
    (_HUB_DIA_MIN - _PRESS_HOLE_MAX) / 2.0
    - PRESS_HOLE_MOUTH_CHAMFER_MAX
    - EDGE_BREAK_MAX_MM
)
if SHOULDER_LAND_WORST <= 0.0:
    raise AssertionError("MHA-PD-28's shoulder keeps no flat land on face A")
