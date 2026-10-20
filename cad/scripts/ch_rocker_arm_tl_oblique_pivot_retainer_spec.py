"""MHA-CH-06-TL-31: fitted removable steel top washer, two off.

Turn from 3/8-in steel, SUPPLY 7 MIN. This is a blank allowance, NOT a
finished 7-mm washer: the native installed model uses the calculated fitted
nominal. Face the underside to the actual loaded carrier/pin running gap
with the headed clevis HELD AGAINST THE UPPER EDGE of the pin cross-hole.
That loading direction includes the complete drilled-hole/clevis clearance.
Both washers, headed clevis pins and fresh bent split cotters are installed
in BOTH pass pairs. No top retainer is a permanent clamp.

Frame: bore axis +Z, bottom running face Z=0, finished top Z=THICKNESS.
Assembly bottom sits at actual carrier top plus its fitted running gap.
The pivot-pin end projects above the carrier plate and workholding; the
setup note requires actual installed toolholder/spindle clearance acceptance.
No native outline supplies the absent installed tooling-envelope authority.
"""

from __future__ import annotations

import math
import _config

import ch_rocker_arm_tl_oblique_retention_spec as retention
from _gtol_planar import PlanarFace
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
DRILLED_BAND = (0.10, 0.0)
PIN_PROJECTION_ABOVE_PLATE = retention.PIN_CARRIER_JOURNAL_LENGTH - CARRIER_THICKNESS
PIN_PROJECTION_ABOVE_WORK = retention.PIN_PROJECTION_ABOVE_WORK_NOMINAL

AXIS_NAME = "RetainerAxis"
BOTTOM_PLANE = "Front Plane"
TOP_PLANE = "RetainerTop"
SUPPLY_REFERENCE = "SupplyReference"
REFERENCE_SKETCHES = (SUPPLY_REFERENCE,)
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
    SUPPLY_REFERENCE: {"SupplyThickness"},
}
DRAWING_PRECISION = {
    "WasherProfile": {"WasherDia": 1, "WasherBore": 2},
    "Washer": {"FinishedThickness": THICKNESS_PLACES},
    SUPPLY_REFERENCE: {"SupplyThickness": 1},
}
DRAWING_PRECISION_BY_NAME = {name: places for row in DRAWING_PRECISION.values() for name, places in row.items()}
DIMENSION_CALLOUTS = {
    "WasherBore": "DRILL THRU; CLEARS TL-23 JOURNAL",
    "FinishedThickness": (
        "REF; FACE UNDERSIDE TO ACTUAL\n"
        f"LOADED RUNNING GAP {RUNNING_GAP_MIN:.2f}-{RUNNING_GAP_MAX:.2f}\n"
        "ON MHA-CH-06-TL-21 CARRIER / TL-23 PIN;\n"
        "HOLD CLEVIS AGAINST UPPER CROSS-HOLE EDGE"
    ),
    "SupplyThickness": "SUPPLY; FINISH TO LOADED GAP",
}
SETUP_NOTE = (
    f"PIN END {PIN_PROJECTION_ABOVE_PLATE:.1f} ABOVE CARRIER PLATE,\n"
    f"ABOUT {PIN_PROJECTION_ABOVE_WORK:.1f} ABOVE WORK TOP (NOMINAL).\n"
    "BOTH RETAINERS LOCKED FOR EITHER PASS; FRESH COTTERS.\n"
    "ACCEPT ACTUAL INSTALLED TOOLHOLDER / SPINDLE CLEARANCE."
)
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
# The washer may turn relative to the carrier under uplift; only its lower
# running face needs a roughness symbol. The upper clevis contact is static.
SURFACE_FINISHES = (SurfaceFinishControl("carrier_running_face", MACHINED_UM, PlanarFace((0.0, 0.0, -1.0), 0.0)),)
