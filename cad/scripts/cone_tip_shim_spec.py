r"""Pure-data contract shared by the MHA-141 cone tip shim pack part and drawing.

User ruling U30 (2026-09-23): the cone tip block (MHA-092) stands on a
blackened carbon-steel shim pack between the swing platform's top face and
its foot, set at fit-up to bring the adjuster axis onto the cone axis. The
pack is cut to the block's footprint, so every size here is the tip block's.
The MHA-140 hold-down screw rises through it into the block's foot tap, so
each leaf carries a #6 clearance hole on the tap axis.
"""

from __future__ import annotations

from _hole_spec import HoleSpec, blind_cut_dia_mm
from cone_tip_block_spec import (
    BLOCK_X,
    BLOCK_Z,
    FOOT_SHIM_RANGE_MM,
    FOOT_THREAD,
    SHIM_NOMINAL,
)

SHIM_X = BLOCK_X
SHIM_Z = BLOCK_Z
SHIM_T = SHIM_NOMINAL  # modelled at the nominal stack
STACK_RANGE_MM = FOOT_SHIM_RANGE_MM
# Handoff BOM: leaves cut from 0.05 / 0.10 / 0.25 / 0.50 mm carbon steel shim
# stock (e.g. a steel shim-stock assortment).
LEAF_STOCK_MM = (0.05, 0.10, 0.25, 0.50)

SCREW_SIZE = FOOT_THREAD.split("-")[0]  # "#6"
HOLE_SPEC = HoleSpec("clearance", SCREW_SIZE, fit="normal")
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)

# U27 / rule 12: the web from the hole to the nearest edge (the 12.0 sides).
MIN_WEB_MM = 1.5
EDGE_WEB_MM = (min(SHIM_X, SHIM_Z) - HOLE_DIA) / 2.0
if EDGE_WEB_MM < 2.0:
    raise ValueError(f"shim hole web {EDGE_WEB_MM:.2f} is under the 2.0 target")
if min(LEAF_STOCK_MM) > STACK_RANGE_MM[0]:
    raise ValueError("the thinnest leaf cannot reach the minimum stack")

MANUFACTURING_NOTES = (
    "SHIM PACK: CUT EACH LEAF FROM CARBON STEEL SHIM STOCK "
    + " / ".join(f"{t:.2f}" for t in LEAF_STOCK_MM)
    + ".\n"
    f"STACK TO FIT {STACK_RANGE_MM[0]:.2f}-{STACK_RANGE_MM[1]:.2f}, "
    f"NOMINAL {SHIM_T:.2f}: SET THE MHA-092 ADJUSTER AXIS ON THE CONE AXIS.\n"
    "BLACKEN ALL LEAVES. DEBURR BOTH FACES; LEAVES MUST LIE FLAT."
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShimProfile": {"Width", "Depth"},
    "Shim": {"Thickness"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShimProfile": {"Width": 1, "Depth": 1},
    "Shim": {"Thickness": 2},
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
