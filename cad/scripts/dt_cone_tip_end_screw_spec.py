r"""Pure-data contract for MHA-DT-39, the cone tip end screw.

Owner decision C1 keyed, 2026-11-09 (PR #1992; ``cone_tip_cluster``): a stock
McMaster 91794A559 (18-8 stainless, 1/4-28 x 3/4 slotted fillister, ASME
B18.6.3) with ONE added operation: drill #52 x .12 concentric in its
threaded end for T006's pivot (MHA-DT-37; owner ruling 2026-11-24, fit audit
question 11: was a .0630 ream).  It threads through MHA-DT-21,
locked by the block's pinch slit; its end face bears on the MHA-DT-38 bushing
and sets the shaft's end play (``cone_stack_end_play.SHAFT_END_PLAY``).  Real
machining, so it keeps the subsystem prefix (subsystem-identities.md).

The hole's wall to the thread root falls under rule 17's .080 target at the
worst case: the minimum minor of the 1/4-28 UNF-2A thread less the largest
drilled hole.  The owner accepts it as a minor exception (RV-01, owner ruling
2026-11-09 via PR #1992, restated for the drilled hole by owner ruling
2026-11-24, fit audit question 11); the sheet states the floored value as a
plain fact on the hole's callout (rule 20).

Local frame: the stock fillister frame, untransformed.  Axis local Y
(``ScrewAxis``, Front Plane ∩ Right Plane), head up, the under-head face at
y = 0 (Top Plane), the threaded end face at y = -SHANK_LEN (``TipFace``).
The hole runs from ``TipFace`` toward +Y.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

import math

import _config
import cone_stack_end_play as end_play
import cone_tip_cluster as tip
import dt_cone_tip_gear_spec as tip_gear
from _fit_deviations import deviations
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _mcmaster_91794a559 import (
    HEAD_DIA,
    HEAD_H,
    PITCH,
    SHANK_DIA,
    SHANK_LEN,
    SKU,
    THREAD,
    THREAD_MINOR_MIN_MM,
)
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm

PART_NAME = "dt-cone-tip-end-screw"
UNIT = drawing_unit(
    "parts/dt-cone-tip-end-screw", _config.parts("dt-cone-tip-end-screw")
)
MM_PER_IN = tip.MM_PER_IN
if SKU != tip.END_SCREW_SKU:
    raise AssertionError(f"MHA-DT-39 stock {SKU} is not {tip.END_SCREW_SKU}")
if THREAD != tip.ADJUSTER_THREAD:
    raise AssertionError(f"MHA-DT-39 thread {THREAD} is not {tip.ADJUSTER_THREAD}")

# Mates quoted to name them (rule 4); the offline test checks the registry.
PIVOT_NUMBER = "MHA-DT-37"
BUSHING_NUMBER = "MHA-DT-38"
BLOCK_NUMBER = "MHA-DT-21"

# --- The added operation ----------------------------------------------------
END_HOLE_DRILL = tip.END_HOLE_DRILL  # #52
END_HOLE_DIA = tip.END_HOLE_DIA_MM  # .0635
END_HOLE_BAND = tip.END_HOLE_BAND  # +.004/-.000, ANALYSIS (DRILLED HOLES row)
END_HOLE_DIA_PLACES = 4
END_HOLE_DEPTH = tip.END_HOLE_DEPTH_MM  # .12, full drilled diameter
END_HOLE_DEPTH_PLACES = 2
END_HOLE_DEPTH_BAND = printed_band_mm(END_HOLE_DEPTH_PLACES, unit=UNIT)
END_HOLE_DIA_MAX = END_HOLE_DIA + deviations(END_HOLE_BAND)[1]
# The stock's flat tip is chamfered 0.7 P (the family law); the hole must
# open inside the flat.
TIP_CHAMFER = 0.7 * PITCH
if END_HOLE_DIA_MAX / 2.0 >= SHANK_DIA / 2.0 - TIP_CHAMFER:
    raise AssertionError("MHA-DT-39 pivot hole breaks into the tip chamfer")

# --- The hole's position on the thread axis ---------------------------------
# Radial offset of the drilled hole from the 1/4-28 thread axis: the screw is
# held on its thread in the lathe and spotted and drilled from the tailstock,
# so the hole runs true to the spindle and the thread runs out in the hold.
# Basis: drawing-guidelines.md "What the shop holds", runout row (.001 per
# inch of feature, never under .001 total indicated): .001 TIR is .0005
# radial.  The drive train's tip error budget reads this.
END_HOLE_POSITION_MM = 0.0005 * MM_PER_IN

# --- Rule 17: wall from the hole to the thread root -------------------------
# The smallest root the 2A thread allows (``_mcmaster_91794a559``'s derived
# minimum minor) over the largest drilled hole, offset by its position error.
END_HOLE_WALL_WORST = (
    THREAD_MINOR_MIN_MM - END_HOLE_DIA_MAX
) / 2.0 - END_HOLE_POSITION_MM
if END_HOLE_WALL_WORST < WALL_FLOOR_MM:
    raise AssertionError(
        f"MHA-DT-39 hole wall {END_HOLE_WALL_WORST / MM_PER_IN:.4f} in under the "
        ".060 floor"
    )
# RV-01 accepts the shortfall under the .080 target; should the wall ever
# reach the target, this refuses so the exception is retired.
if END_HOLE_WALL_WORST >= WALL_TARGET_MM:
    raise AssertionError("MHA-DT-39 hole wall meets .080: retire RV-01")
# A MIN never rounds up: floored to the printed thousandth.
END_HOLE_WALL_PRINTED_IN = (
    math.floor(round(END_HOLE_WALL_WORST / MM_PER_IN * 1000.0, 6)) / 1000.0
)

# --- The pivot in the hole ----------------------------------------------------
# Running clearance, from the contract's printed limits.
PIVOT_CLEARANCE = tip.PIVOT_RUNNING_CLEARANCE_MM
# The pivot stands PIVOT_LENGTH north of T006's leaves; the bushing, pressed
# against those leaves, covers BUSHING_LENGTH of it.  The pivot length's grade
# is MHA-DT-37's authored precision, so a regrade there reruns this stack.
PIVOT_LENGTH_BAND = printed_band_mm(
    tip_gear.DRAWING_PRECISION["Pivot"]["PivotLength"], unit=tip_gear.UNIT
)
BUSHING_LENGTH_BAND = printed_band_mm(tip.BUSHING_PLACES, unit="in")
PIVOT_PROUD_MAX = (tip.PIVOT_LENGTH_MM + PIVOT_LENGTH_BAND) - (
    tip.BUSHING_LENGTH_MM - BUSHING_LENGTH_BAND
)
PIVOT_PROUD_MIN = (tip.PIVOT_LENGTH_MM - PIVOT_LENGTH_BAND) - (
    tip.BUSHING_LENGTH_MM + BUSHING_LENGTH_BAND
)
# At fit-up the screw is run in until the shaft just stops, so its end face
# can touch the bushing: the pivot never bottoms in the shallowest hole.
PIVOT_FLOOR_AIR_MIN = (END_HOLE_DEPTH - END_HOLE_DEPTH_BAND) - PIVOT_PROUD_MAX
if PIVOT_FLOOR_AIR_MIN <= 0.0:
    raise AssertionError(
        f"MHA-DT-37 pivot bottoms in the MHA-DT-39 hole ({PIVOT_FLOOR_AIR_MIN:.3f} mm)"
    )
# The MHA-DT-38 length is the stack term that needs its third place: at the
# title block's .XX band the pivot could bottom (MHA-DT-38's length callout
# names this stack).
_PIVOT_FLOOR_AIR_AT_XX = (END_HOLE_DEPTH - END_HOLE_DEPTH_BAND) - (
    (tip.PIVOT_LENGTH_MM + PIVOT_LENGTH_BAND)
    - (tip.BUSHING_LENGTH_MM - printed_band_mm(2, unit="in"))
)
if _PIVOT_FLOOR_AIR_AT_XX > 1e-9:  # zero air: the pivot touches the floor
    raise AssertionError("MHA-DT-38 length holds the pivot air at .XX: print .XX")
# Backed off to the largest end play, with the hole mouth's general edge
# break, the shortest pivot still runs in the drilled hole.
HOLE_MOUTH_BREAK_MAX = edge_break_chamfer_mm(unit=UNIT)
PIVOT_ENGAGEMENT_MIN = (
    PIVOT_PROUD_MIN - end_play.SHAFT_END_PLAY[1] - HOLE_MOUTH_BREAK_MAX
)
if PIVOT_ENGAGEMENT_MIN <= 0.0:
    raise AssertionError(
        f"MHA-DT-37 pivot engages the MHA-DT-39 hole only {PIVOT_ENGAGEMENT_MIN:.3f} mm"
    )

# Rule 18 (the screw's full thread in MHA-DT-21) is the block's proof:
# dt_cone_tip_block_spec.END_SCREW_ENGAGEMENT_MIN_MM.


def inch_text(value_mm: float, places: int) -> str:
    """An mm length as ASME decimal-inch text (no leading zero)."""
    text = f"{value_mm / MM_PER_IN:.{places}f}"
    return text[1:] if text.startswith("0.") else text


# Below the hole's imported diameter (four places, no band: a drilled hole
# prints its drill), rules 12 and 26: the drill and the depth (PR 2 r7
# machinist review: the depth belongs in the callout; the depth the
# model's at its drawing places).  Then rule 7's two lines of words: the
# flag to note END_HOLE_NOTE, which names the mate by drawing number and
# says it is turned to run in the hole as drilled, and the wall shortfall as
# a plain fact in rule 20's own form (RV-01; the hole's one wall is to the
# thread root).  The hole is drilled #52 with no band (owner ruling
# 2026-11-24, fit audit question 11) and rule 4 form 2 holds for the pivot:
# MHA-DT-37 prints it as a reference turned last to this hole and the
# reamed MHA-DT-38 bushing at once, with both clearances (running
# PIVOT_CLEARANCE, .0013-.0063). D47, delegated ruling 2026-11-26 (Main),
# precedent: the owner's question-11 ruling 2026-11-24 and the made-to-fit
# form of the owner-approved fit policy; owner review #2144: the two sheets
# say the same thing.  The fit is a flag note because on one row it is
# wider than the 72 mm between the frame and the head's outline (machinist
# review r1, farm run 20261124T110807008Z: three rows of words broke rule 7).
END_HOLE_NOTE = 3
END_HOLE_DEPTH_TEXT = inch_text(END_HOLE_DEPTH, END_HOLE_DEPTH_PLACES)
END_HOLE_CALLOUT = "\n".join(
    (
        f"{END_HOLE_DRILL} DRILL <HOLE-DEPTH> {END_HOLE_DEPTH_TEXT}",
        f"SEE NOTE {END_HOLE_NOTE}",
        f"WALL {inch_text(END_HOLE_WALL_PRINTED_IN * MM_PER_IN, 3)} MIN",
    )
)

# The stock, named once (rule 7: a flagged note, no method).
STOCK_NOTE = "\n".join(
    (
        f"1. MAKE FROM McMASTER-CARR {SKU}, {THREAD} X 3/4 SLOTTED FILLISTER",
        "   HEAD SCREW; ADD THE DRILLED HOLE ONLY.",
        "2. UNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE.",
        f"{END_HOLE_NOTE}. {PIVOT_NUMBER} PIVOT IS TURNED TO RUN IN THIS HOLE AS DRILLED.",
    )
)

# Model-owned drawing controls: a plain cut-extrude, its sketch circle the
# drilled diameter (the sheet imports it) and the cut's blind depth the
# full-diameter depth (its places set the callout's depth text).
HOLE_FEATURE = "EndHoleProfile"
HOLE_CUT = "EndHole"
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    HOLE_FEATURE: {"EndHoleDia"},
    HOLE_CUT: {"EndHoleDepth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    HOLE_FEATURE: {"EndHoleDia": END_HOLE_DIA_PLACES},
    HOLE_CUT: {"EndHoleDepth": END_HOLE_DEPTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-DT-39 dimension needs authored places")

TIP_FACE = "TipFace"
# Stock envelope, for the drawing's layout only.
OVERALL_LENGTH = SHANK_LEN + HEAD_H
HEAD_RADIUS = HEAD_DIA / 2.0
ISOMETRIC_VIEW_SCALE = (2, 1)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
