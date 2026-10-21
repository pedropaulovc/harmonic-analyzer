"""MHA-CH-06-TL-31: fitted removable steel top washer, two off.

Turn from 3/8-in steel, SUPPLY 7 MIN. This is a blank allowance, NOT a
finished 7-mm washer: the native installed model uses the calculated fitted
nominal. Its actual-thickness REF callout carries the supply allowance;
there is no dimension to an undrawn blank. Face the Ra 1.6 underside to the
actual loaded carrier/pin running gap with the headed clevis HELD AGAINST
THE UPPER EDGE of the pin cross-hole, including the complete drilled-hole/
clevis clearance.
Both washers, headed clevis pins and fresh bent split cotters are installed
in BOTH pass pairs. No top retainer is a permanent clamp.

Frame: bore axis +Z, bottom running face Z=0, finished top Z=THICKNESS.
Assembly bottom sits at actual carrier top plus its fitted running gap.
Pin-end projection, both-retainer locking, fresh cotters and installed
toolholder/spindle clearance acceptance are assembly facts: the jig
assembly's caption and capture steps carry them, not this part sheet.
"""

from __future__ import annotations

import math
import _config

import ch_rocker_arm_tl_oblique_retention_spec as retention
from _gtol_planar import PlanarFace
from _printed_tolerance import drilled_oversize_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

OUTER_DIA = retention.TOP_WASHER_OD
BORE_DIA = retention.TOP_WASHER_BORE
SUPPLY_MIN_THICKNESS = retention.TOP_WASHER_SUPPLY_MIN_THICKNESS
THICKNESS = retention.TOP_WASHER_NOMINAL_THICKNESS
THICKNESS_PLACES = 2  # reference nominal only; actual loaded gap controls
EDGE_BREAK_MAX = float(_config.title_block("edge_break")["chamfer_max_mm"])
STOCK_THICKNESS = 3.0 / 8.0 * 25.4
STOCK_WIDTH = 25.4
CARRIER_THICKNESS = retention.CARRIER_THICKNESS
CROSS_HOLE_FROM_SEAT = retention.PIN_CROSS_HOLE_FROM_SEAT
CROSS_HOLE_DIA = retention.PIN_CROSS_HOLE_DIA
CLEVIS_DIA = retention.PIN_CLEVIS_NOMINAL_DIAMETER
RUNNING_GAP_MIN, RUNNING_GAP_MAX = retention.TOP_RUNNING_GAP
# The bore prints DRILL with no band of its own: the title block's DRILLED
# HOLES row is its whole tolerance, 10.20-10.30 (rule 3).
DRILLED_BAND = (drilled_oversize_mm(), 0.0)
if DRILLED_BAND != (0.10, 0.0):
    raise AssertionError("the DRILLED HOLES row no longer holds the 10.20-10.30 journal clearance")

AXIS_NAME = "RetainerAxis"
BOTTOM_PLANE = "Front Plane"
TOP_PLANE = "RetainerTop"
VOLUME_MM3 = math.pi / 4.0 * (OUTER_DIA**2 - BORE_DIA**2) * THICKNESS


def loaded_running_gap(
    thickness: float, *, cross_hole_from_seat: float = CROSS_HOLE_FROM_SEAT,
    cross_hole_dia: float = CROSS_HOLE_DIA, clevis_dia: float = CLEVIS_DIA,
    carrier_thickness: float = CARRIER_THICKNESS,
) -> float:
    """Washer uplift until clevis touches the UPPER cross-hole edge."""
    return cross_hole_from_seat + cross_hole_dia / 2.0 - clevis_dia - carrier_thickness - thickness


def require_loaded_running_gap(thickness: float, **actual: float) -> float:
    gap = loaded_running_gap(thickness, **actual)
    if not RUNNING_GAP_MIN - 1e-9 <= gap <= RUNNING_GAP_MAX + 1e-9:
        raise ValueError("retainer must be faced to the actual upper-edge-loaded running gap")
    return gap


if not 0.0 < THICKNESS < SUPPLY_MIN_THICKNESS < STOCK_THICKNESS:
    raise AssertionError("supply allowance must not become the finished washer thickness")
NOMINAL_RUNNING_GAP = require_loaded_running_gap(THICKNESS)
DRAWING_DIMENSIONS = {
    "WasherProfile": {"WasherDia", "WasherBore"},
    "Washer": {"FinishedThickness"},
}
DRAWING_PRECISION = {
    "WasherProfile": {"WasherDia": 1, "WasherBore": 2},
    "Washer": {"FinishedThickness": THICKNESS_PLACES},
}
DRAWING_PRECISION_BY_NAME = {name: places for row in DRAWING_PRECISION.values() for name, places in row.items()}
DIMENSION_CALLOUTS = {
    "WasherBore": "DRILL THRU; CLEARS TL-23 JOURNAL",
    "FinishedThickness": (
        f"REF; SUPPLY {SUPPLY_MIN_THICKNESS:.1f} MIN THICK; FACE Ra {MACHINED_UM:.1f} SIDE\n"
        f"TO ACTUAL LOADED RUNNING GAP {RUNNING_GAP_MIN:.2f}-{RUNNING_GAP_MAX:.2f}\n"
        "ON MHA-CH-06-TL-21 CARRIER / TL-23 PIN;\n"
        "HOLD CLEVIS AGAINST UPPER CROSS-HOLE EDGE"
    ),
}
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
# The washer may turn relative to the carrier under uplift; only its lower
# running face needs a roughness symbol. The upper clevis contact is static.
SURFACE_FINISHES = (SurfaceFinishControl("carrier_running_face", MACHINED_UM, PlanarFace((0.0, 0.0, -1.0), 0.0)),)
