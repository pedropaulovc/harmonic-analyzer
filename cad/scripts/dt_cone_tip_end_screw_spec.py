r"""Pure-data contract for MHA-DT-39, the cone tip end screw.

Owner decision C1 keyed, 2026-11-09 (PR #1992; ``cone_tip_cluster``): a stock
McMaster 91794A558 (18-8 stainless, 1/4-28 x 5/8 slotted fillister, ASME
B18.6.3) with ONE added operation: drill and ream Ø.0630 x .12 concentric in
its threaded end for T006's pivot (MHA-DT-37).  It threads through MHA-DT-21,
locked by the block's pinch slit; its end face bears on the MHA-DT-38 bushing
and sets the shaft's end play (``cone_stack_end_play.SHAFT_END_PLAY``).  Real
machining, so it keeps the subsystem prefix (subsystem-identities.md).

The hole's wall to the thread root falls under rule 17's .080 target at the
worst case: the minimum minor of the 1/4-28 UNF-2A thread less the largest
reamed hole.  The owner accepts it as a minor exception (RV-01, owner ruling
2026-11-09 via PR #1992); the sheet states the floored value as a plain fact
on the hole's callout (rule 20).

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
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _mcmaster_91794a558 import (
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
END_HOLE_DIA = tip.END_HOLE_DIA_MM  # .0630 reamer
END_HOLE_BAND = tip.END_HOLE_BAND  # +.0005/-.0000
END_HOLE_DIA_PLACES = 4
END_HOLE_DEPTH = tip.END_HOLE_DEPTH_MM  # .12, full reamed diameter
END_HOLE_DEPTH_PLACES = 2
END_HOLE_DEPTH_BAND = printed_band_mm(END_HOLE_DEPTH_PLACES, unit=UNIT)
END_HOLE_DIA_MAX = END_HOLE_DIA + max(END_HOLE_BAND)
# The stock's flat tip is chamfered 0.7 P (the family law); the hole must
# open inside the flat.
TIP_CHAMFER = 0.7 * PITCH
if END_HOLE_DIA_MAX / 2.0 >= SHANK_DIA / 2.0 - TIP_CHAMFER:
    raise AssertionError("MHA-DT-39 pivot hole breaks into the tip chamfer")

# --- The hole's position on the thread axis ---------------------------------
# Radial offset of the reamed hole from the 1/4-28 thread axis: the screw is
# held on its thread in the lathe and drilled and reamed from the tailstock,
# so the hole runs true to the spindle and the thread runs out in the hold.
# Basis: drawing-guidelines.md "What the shop holds", runout row (.001 per
# inch of feature, never under .001 total indicated): .001 TIR is .0005
# radial.  The drive train's tip error budget reads this.
END_HOLE_POSITION_MM = 0.0005 * MM_PER_IN

# --- Rule 17: wall from the hole to the thread root -------------------------
# The smallest root the 2A thread allows (``_mcmaster_91794a558``'s derived
# minimum minor) over the largest reamed hole, offset by its position error.
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
# against those leaves, covers BUSHING_LENGTH of it.  ASSUMPTION: MHA-DT-37
# prints the pivot length at the title block's .XX (cone_tip_cluster: ".XX").
PIVOT_LENGTH_BAND = printed_band_mm(2, unit="in")
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
# Backed off to the largest end play, with the hole mouth's general edge
# break, the shortest pivot still runs in the reamed hole.
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


def _floor_text(value_mm: float, places: int) -> str:
    scaled = math.floor(round(value_mm / MM_PER_IN * 10**places, 6))
    return inch_text(scaled / 10**places * MM_PER_IN, places)


def _ceil_text(value_mm: float, places: int) -> str:
    scaled = math.ceil(round(value_mm / MM_PER_IN * 10**places, 6))
    return inch_text(scaled / 10**places * MM_PER_IN, places)


# Rule 12: the process; rule 4: the fit and its mate by drawing number, the
# clearance REF; rule 20: the wall shortfall as a plain fact (RV-01).  The
# reamed depth is its own model dimension in the section.
END_HOLE_CALLOUT = "\n".join(
    (
        "REAM",
        f"RUNNING FIT ON {PIVOT_NUMBER} PIVOT"
        f" (CLEARANCE {_floor_text(PIVOT_CLEARANCE[0], 4)}-"
        f"{_ceil_text(PIVOT_CLEARANCE[1], 4)} REF)",
        f"WALL TO THREAD ROOT {END_HOLE_WALL_PRINTED_IN:.3f}".replace("0.", ".", 1)
        + " MIN",
    )
)
END_HOLE_DEPTH_CALLOUT = "FULL DIA"

# The stock, named once (rule 7: a flagged note, no method).
STOCK_NOTE = "\n".join(
    (
        f"1. MAKE FROM McMASTER-CARR {SKU}, {THREAD} X 5/8 SLOTTED FILLISTER",
        "   HEAD SCREW, 18-8 STAINLESS STEEL; ADD THE REAMED HOLE ONLY.",
        "2. UNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE.",
    )
)

# Model-owned drawing controls: one revolve-cut profile carries both sizes.
HOLE_FEATURE = "EndHoleProfile"
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    HOLE_FEATURE: {"EndHoleDia", "EndHoleDepth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    HOLE_FEATURE: {
        "EndHoleDia": END_HOLE_DIA_PLACES,
        "EndHoleDepth": END_HOLE_DEPTH_PLACES,
    },
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
