r"""Pure-data contract shared by the MHA-141 cone tip shim pack part and drawing.

User ruling U30 (2026-09-23): the cone tip block (MHA-092) stands on a
blackened carbon-steel shim pack between the swing platform's top face and
its foot, set at fit-up to bring the adjuster axis onto the cone axis. The
pack is cut to the block's foot face -- the footprint, with the I31 foot
flange, less the heel relief -- so every size here is the tip block's.

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
from _hole_spec import THREAD_MAJOR_MM
from cone_tip_block_spec import (
    BLOCK_DEPTH_PLACES,
    BLOCK_X,
    BLOCK_Z,
    DRAWING_PRECISION as BLOCK_DRAWING_PRECISION,
    FLANGE_LEN,
    FLANGE_SLOT_END_PLACES,
    FLANGE_SLOT_FLOAT,
    FLANGE_SLOT_NORTH_Z,
    FLANGE_SLOT_W_MAX,
    FOOT_SHIM_RANGE_MM,
    FOOT_THREAD,
    HEEL_RELIEF_DEPTH,
    SHIM_NOMINAL,
)

SHIM_X = BLOCK_X
# I31 (Main, 2026-09-25): the block's north-bottom heel is relieved for the
# cone pivot screw's head, so the pack stops at the relief's inner face; left
# full length it would reach under the head the relief clears.  I31 option
# 1: it runs south under the foot flange to the flange's end.  Edges are in
# the block frame (+Z north), origin on the block centre.
SHIM_NORTH_Z = BLOCK_Z / 2.0 - HEEL_RELIEF_DEPTH
SHIM_SOUTH_Z = -BLOCK_Z / 2.0 - FLANGE_LEN
SHIM_Z = SHIM_NORTH_Z - SHIM_SOUTH_Z
SHIM_T = SHIM_NOMINAL  # modelled at the nominal stack
STACK_RANGE_MM = FOOT_SHIM_RANGE_MM
# Handoff BOM: leaves cut from 0.05 / 0.10 / 0.25 / 0.50 mm carbon steel shim
# stock (e.g. a steel shim-stock assortment).
LEAF_STOCK_MM = (0.05, 0.10, 0.25, 0.50)

_GENERAL_1PL_MM = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
_GENERAL_2PL_MM = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
_BAND_BY_PLACES = {1: _GENERAL_1PL_MM, 2: _GENERAL_2PL_MM}
# The slot opens to the south edge, along the block's flange slot.
SLOT_OPEN_EDGE = "south"
# Width (.XX): its narrowest print still spans the flange slot's widest cut,
# so a pack laid square under the block never narrows the screw's passage.
SLOT_W = math.ceil((FLANGE_SLOT_W_MAX + _GENERAL_2PL_MM) * 100.0 - 1e-6) / 100.0
SLOT_R = SLOT_W / 2.0  # full radius at the closed end
_SLOT_R_MIN = (SLOT_W - _GENERAL_2PL_MM) / 2.0
_SCREW_R = THREAD_MAJOR_MM[FOOT_THREAD] / 2.0
# The closed end's radius centre, located (.X) from the pack's north edge.
# The fitter squares the north edge on the block's heel-relief face, so the
# screw's farthest reach north of that edge runs through the block's prints
# (heel relief .XX, Depth .X, and the flange slot's north arc centre
# FlangeSlotNorthZ, baselined from the body's south face at .X since #838
# r3) plus the screw's float in the flange slot.  The old chain went through
# the slot midpoint FlangeSlotZ (.X) and half the .XX spacing; the block no
# longer prints either.  The radius end must pass it
# with the narrowest slot (the screw can sit that slot's slack past the
# radius centre) and the location at its long limit.
_HEEL_DEPTH_PLACES = BLOCK_DRAWING_PRECISION["HeelReliefProfile"]["HeelReliefDepth"]
_NORTH_END_PLACES = BLOCK_DRAWING_PRECISION["FlangeSlotNorthReference"][
    "FlangeSlotNorthZ"
]
if _NORTH_END_PLACES != FLANGE_SLOT_END_PLACES:
    raise ValueError("the block's FlangeSlotNorthZ places moved off its spec")
FLANGE_SLOT_NORTH_CENTRE_FROM_NORTH = (
    SHIM_NORTH_Z + BLOCK_Z / 2.0 + FLANGE_SLOT_NORTH_Z
)
SCREW_NORTH_REACH_BANDS_MM = (
    _BAND_BY_PLACES[_HEEL_DEPTH_PLACES]
    + _BAND_BY_PLACES[BLOCK_DEPTH_PLACES]
    + _BAND_BY_PLACES[_NORTH_END_PLACES]
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
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShimProfile": {"Width": 1, "Depth": 1},
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

# Rule 6: a note never carries a dimension.  The stack range IS the
# thickness requirement, so it rides the thickness dimension's own text,
# around the model's nominal: "0.05–2.20 STACK (1.10 NOM)".  The drawing
# sets these as the dimension's prefix and suffix; the value between them
# is the imported model dimension at its model-owned places (Main's eye
# pass of warm-c486).  The leaf stock is the material specification and
# blackening the finish (rule 1), so the sheet carries no general note; how
# the leaves go in is a fit-up step in the MHA-A03 sequence (Codex P2 on
# #857).
_THICKNESS_PLACES = DRAWING_PRECISION["Shim"]["Thickness"]
THICKNESS_TEXT_PREFIX = (
    f"{STACK_RANGE_MM[0]:.{_THICKNESS_PLACES}f}"
    f"–{STACK_RANGE_MM[1]:.{_THICKNESS_PLACES}f} STACK ("
)
THICKNESS_TEXT_SUFFIX = " NOM)"
