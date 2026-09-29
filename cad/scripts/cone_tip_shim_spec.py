r"""Pure-data contract shared by the MHA-141 cone tip shim pack part and drawing.

User ruling U30 (2026-09-23): the cone tip block (MHA-092) stands on a
blackened carbon-steel shim pack between the swing platform's top face and
its foot, set at fit-up to bring the adjuster axis onto the cone axis. The
pack is cut to the block's complete foot face: the south flange through to
the north face. The heel relief is gone, so the pack has no notch.

Main's ruling on the passage (2026-09-24): a HORSESHOE, not a hole.  Stacking
to 0.05 is iterative; with an open slot the leaves slide in or out with the
hold-down slack, instead of the screw coming out and the block lifting each
time.  I31 (Main, 2026-09-25): the block now has a south foot flange, the pack
runs under it to the flange's end, and the MHA-140 screw rises through the
flange's axial slot wherever the fit-up puts it.  So the horseshoe opens SOUTH
along that slot, at least as wide as it, and its full-radius closed end sits
north of every place the screw can reach.
"""

from __future__ import annotations

import math

import _config
from _printed_tolerance import printed_band_mm
from _hole_spec import THREAD_MAJOR_MM
from cone_tip_block_spec import (
    BLOCK_DEPTH_PLACES,
    BLOCK_X,
    BLOCK_Z,
    BUSHING_DEPTH_PLACES,
    COLLAR_WIDTH_PLACES,
    DRAWING_PRECISION as BLOCK_DRAWING_PRECISION,
    FLANGE_LEN,
    FLANGE_SLOT_END_PLACES,
    FLANGE_SLOT_FLOAT,
    FLANGE_SLOT_NORTH_Z,
    FLANGE_SLOT_W_MAX,
    FOOT_SHIM_RANGE_MM,
    FOOT_THREAD,
    GEAR_STACK_NORTH_FACE_BAND_MM,
    SHIM_NOMINAL,
    TIP_FEELER_SET_BAND_MM,
)
from cone_line import PIVOT_STATION, TIP_BLOCK_STATION
from cone_pivot_screw_spec import HEAD_DIA, SHOULDER_DIA
from cone_swing_platform_spec import PIVOT_HOLE_DIA

SHIM_X = BLOCK_X
# The pack reaches the north face of the unrelieved body and the south end
# of the foot flange. Edges are in the block frame (+Z north).
SHIM_NORTH_Z = BLOCK_Z / 2.0
SHIM_SOUTH_Z = -BLOCK_Z / 2.0 - FLANGE_LEN
SHIM_Z = SHIM_NORTH_Z - SHIM_SOUTH_Z
SHIM_T = SHIM_NOMINAL  # modelled at the nominal stack
STACK_RANGE_MM = FOOT_SHIM_RANGE_MM
# Handoff BOM: leaves cut from 0.05 / 0.10 / 0.25 / 0.50 mm carbon steel shim
# stock (e.g. a steel shim-stock assortment).
LEAF_STOCK_MM = (0.05, 0.10, 0.25, 0.50)

_GENERAL_1PL_MM = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
_GENERAL_2PL_MM = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
_BAND_BY_PLACES = {1: _GENERAL_1PL_MM, 2: _GENERAL_2PL_MM, 3: printed_band_mm(3)}
# The slot opens to the south edge, along the block's flange slot.
SLOT_OPEN_EDGE = "south"
# Width (.XX): its narrowest print still spans the flange slot's widest cut,
# so a pack laid square under the block never narrows the screw's passage.
SLOT_W = math.ceil((FLANGE_SLOT_W_MAX + _GENERAL_2PL_MM) * 100.0 - 1e-6) / 100.0
SLOT_R = SLOT_W / 2.0  # full radius at the closed end
_SLOT_R_MIN = (SLOT_W - _GENERAL_2PL_MM) / 2.0
_SCREW_R = THREAD_MAJOR_MM[FOOT_THREAD] / 2.0
# The fitter squares the pack's north edge on the block's north face. The
# screw's farthest north reach follows the body's printed depth and the
# north arc-centre location, plus the screw's float in the flange slot. The
# shim slot's radius end must pass it at its narrowest and longest print.
_NORTH_END_PLACES = BLOCK_DRAWING_PRECISION["FlangeSlotNorthReference"][
    "FlangeSlotNorthZ"
]
if _NORTH_END_PLACES != FLANGE_SLOT_END_PLACES:
    raise ValueError("the block's FlangeSlotNorthZ places moved off its spec")
FLANGE_SLOT_NORTH_CENTRE_FROM_NORTH = (
    SHIM_NORTH_Z + BLOCK_Z / 2.0 + FLANGE_SLOT_NORTH_Z
)
SCREW_NORTH_REACH_BANDS_MM = (
    _BAND_BY_PLACES[BLOCK_DEPTH_PLACES] + _BAND_BY_PLACES[_NORTH_END_PLACES]
)
SCREW_NORTH_REACH_FROM_NORTH = FLANGE_SLOT_NORTH_CENTRE_FROM_NORTH - (
    SCREW_NORTH_REACH_BANDS_MM + FLANGE_SLOT_FLOAT
)
SLOT_CENTRE_FROM_NORTH = (
    math.floor(
        (SCREW_NORTH_REACH_FROM_NORTH + (_SLOT_R_MIN - _SCREW_R) - _GENERAL_1PL_MM)
        * 10.0
        + 1e-6
    )
    / 10.0
)
SLOT_CENTRE_Z = SHIM_NORTH_Z - SLOT_CENTRE_FROM_NORTH  # block frame
if SLOT_W - _GENERAL_2PL_MM < FLANGE_SLOT_W_MAX - 1e-9:
    raise ValueError("the shim slot can print narrower than the flange slot")
if (
    SLOT_CENTRE_FROM_NORTH + _GENERAL_1PL_MM - (_SLOT_R_MIN - _SCREW_R)
    > SCREW_NORTH_REACH_FROM_NORTH + 1e-9
):
    raise ValueError("the screw can reach the shim slot's closed end")

# U27 / rule 12: the side webs either side of the slot and the closed end's.
MIN_WEB_MM = 1.5
SIDE_WEB_MM = SHIM_X / 2.0 - SLOT_R
if SIDE_WEB_MM < 2.0:
    raise ValueError(f"shim side web {SIDE_WEB_MM:.2f} is under the 2.0 target")
# The closed end: from the radius apex to the north edge.
END_WEB_MM = SLOT_CENTRE_FROM_NORTH - SLOT_R
if END_WEB_MM < 2.0:
    raise ValueError(f"shim end web {END_WEB_MM:.2f} is under the 2.0 target")
if min(LEAF_STOCK_MM) > STACK_RANGE_MM[0]:
    raise ValueError("the thinnest leaf cannot reach the minimum stack")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShimProfile": {"Width", "Depth"},
    "Shim": {"Thickness"},
    "SlotProfile": {"SlotWidth"},
    # Construction-only sketches, saved hidden, that locate the slot's radius
    # centre from the +X edge and the plan's lower (+Z, north) edge.  They
    # are toleranced .X locations the machinist works to, so the model owns
    # them and their places (Codex P1 on #857).
    "SlotCentreXReference": {"SlotCentreX"},
    "SlotCentreZReference": {"SlotCentreZ"},
}
SHIM_DEPTH_PLACES = 2
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShimProfile": {"Width": 1, "Depth": SHIM_DEPTH_PLACES},
    "Shim": {"Thickness": 2},
    "SlotProfile": {"SlotWidth": 2},
    "SlotCentreXReference": {"SlotCentreX": 1},
    "SlotCentreZReference": {"SlotCentreZ": 1},
}
REFERENCE_SKETCHES = ("SlotCentreXReference", "SlotCentreZReference")
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}

# The full-north-face shim reaches toward the pivot head. Its printed Depth
# can exceed the nominal model: reserve that entire deviation after the
# collar, gear, bushing, feeler, block and pivot-hole print excursions.
# The .XX depth keeps at least 0.20 mm air without a heel relief or field trim.
_BLOCK_NORTH_TRAVEL_MM = (
    printed_band_mm(COLLAR_WIDTH_PLACES)
    + GEAR_STACK_NORTH_FACE_BAND_MM
    + printed_band_mm(BUSHING_DEPTH_PLACES)
    + TIP_FEELER_SET_BAND_MM
    + printed_band_mm(BLOCK_DEPTH_PLACES)
)
_PIVOT_HOLE_PLUS_MM = float(
    str(_config.title_block("drilled_hole")["display_plus"]).lstrip("+")
)
_PIVOT_HEAD_FLOAT_MM = (
    PIVOT_HOLE_DIA + _PIVOT_HOLE_PLUS_MM - SHOULDER_DIA
) / 2.0
PIVOT_HEAD_NOMINAL_AIR_MM = (
    PIVOT_STATION - TIP_BLOCK_STATION - BLOCK_Z / 2.0 - HEAD_DIA / 2.0
)
PIVOT_HEAD_SHIM_AIR_WORST_MM = (
    PIVOT_HEAD_NOMINAL_AIR_MM
    - _BLOCK_NORTH_TRAVEL_MM
    - _PIVOT_HEAD_FLOAT_MM
    - printed_band_mm(SHIM_DEPTH_PLACES)
)
if PIVOT_HEAD_SHIM_AIR_WORST_MM < 0.20:
    raise ValueError("shim north edge can hit the cone pivot head")

# Rule 6: a note never carries a dimension.  The stack range IS the
# thickness requirement, so it rides the thickness dimension's own text,
# around the model's nominal: "0.05–2.20 STACK (1.10 NOM)".  The drawing
# sets these as the dimension's prefix and suffix; the value between them
# is the imported model dimension at its model-owned places (Main's eye
# pass of warm-c486).  The leaf stock is the material specification and
# blackening the finish (rule 1).  How the leaves go in is a fit-up step in
# the MHA-A03 sequence, so the sheet's one general note points at that step
# (Codex P2 on #857) and carries no numbers of its own.
_THICKNESS_PLACES = DRAWING_PRECISION["Shim"]["Thickness"]
THICKNESS_TEXT_PREFIX = (
    f"{STACK_RANGE_MM[0]:.{_THICKNESS_PLACES}f}"
    f"–{STACK_RANGE_MM[1]:.{_THICKNESS_PLACES}f} STACK ("
)
THICKNESS_TEXT_SUFFIX = " NOM)"

# The part's note property.  The sheet appends the pointer to the MHA-A03
# step that stacks the pack (draw_cone_tip_shim), from the step registry: a
# pointer is sheet text, so renumbering the sequence never re-keys the part
# (Main's TbPB ruling 2, 2026-09-27; test_part_isolation).
MANUFACTURING_NOTES = "STACK SET AT ASSEMBLY"
