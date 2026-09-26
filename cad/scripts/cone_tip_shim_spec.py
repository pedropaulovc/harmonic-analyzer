r"""Pure-data contract shared by the MHA-141 cone tip shim pack part and drawing.

User ruling U30 (2026-09-23): the cone tip block (MHA-092) stands on a
blackened carbon-steel shim pack between the swing platform's top face and
its foot, set at fit-up to bring the adjuster axis onto the cone axis. The
pack is cut to the block's footprint, so every size here is the tip block's.
The MHA-140 hold-down screw rises through it into the block's foot tap.

Main's ruling on the passage (2026-09-24): a HORSESHOE, not a hole.  Stacking
to 0.05 is iterative; with an open slot the fitter backs the screw off a few
turns and slides leaves in or out, instead of removing the screw and lifting
the block each time.  The slot is #6 normal clearance wide and ends in a full
radius on the screw axis.  It opens to the block's local -X face, away from
the drum: see ``SLOT_OPEN_SIDE``.
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
from drive_train_steps import step_ref

SHIM_X = BLOCK_X
SHIM_Z = BLOCK_Z
SHIM_T = SHIM_NOMINAL  # modelled at the nominal stack
STACK_RANGE_MM = FOOT_SHIM_RANGE_MM
# Handoff BOM: leaves cut from 0.05 / 0.10 / 0.25 / 0.50 mm carbon steel shim
# stock (e.g. a steel shim-stock assortment).
LEAF_STOCK_MM = (0.05, 0.10, 0.25, 0.50)

SCREW_SIZE = FOOT_THREAD.split("-")[0]  # "#6"
# The slot width is the #6 normal clearance of the shared hole table
# (_hole_spec.CLEARANCE_MM), the source every clearance passage reads.
SLOT_SPEC = HoleSpec("clearance", SCREW_SIZE, fit="normal")
SLOT_W = blind_cut_dia_mm(SLOT_SPEC)
SLOT_R = SLOT_W / 2.0  # full radius, centred on the screw axis
# Local -X, the east face.  The block's +X face looks west, at the drum:
# the platform's narrow west flank ends 2.1-3.6 past it, and beyond stand
# the cylinder's north end disc and the north arbor pedestal.  Past the -X
# face the east flank carries 8.9-9.4 of clear plate, with nothing standing
# on it at foot level (build_drive_train_assembly at TIP_BLOCK_STATION; the
# PR body has the numbers).
SLOT_OPEN_SIDE = -1

# U27 / rule 12: the side webs either side of the slot (12.0 across).
MIN_WEB_MM = 1.5
SIDE_WEB_MM = (SHIM_Z - SLOT_W) / 2.0
if SIDE_WEB_MM < 2.0:
    raise ValueError(f"shim side web {SIDE_WEB_MM:.2f} is under the 2.0 target")
# The closed end: from the radius apex to the +X face.
END_WEB_MM = SHIM_X / 2.0 - SLOT_R
if END_WEB_MM < 2.0:
    raise ValueError(f"shim end web {END_WEB_MM:.2f} is under the 2.0 target")
if min(LEAF_STOCK_MM) > STACK_RANGE_MM[0]:
    raise ValueError("the thinnest leaf cannot reach the minimum stack")

# The MHA-A03 step that stacks the pack under the tip block at fit-up.  The
# sheet cites it through the registry, so a renumbered sequence carries the
# pointer with it (Codex P2 on #857: the fitting method lives in that step).
FIT_UP_STEP = "post-and-tip-block"

# Rule 6: at most four short lines.  The leaf stock is the material
# specification; blackening is the finish.
MANUFACTURING_NOTES = (
    f"SHIM PACK, STACK TO FIT {STACK_RANGE_MM[0]:.2f}-{STACK_RANGE_MM[1]:.2f}, "
    f"NOMINAL {SHIM_T:.2f}.\n"
    "HORSESHOE; SLIDE LEAVES IN WITH SCREW BACKED OFF.\n"
    f"STACK SET AT ASSEMBLY, {step_ref(FIT_UP_STEP)}."
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShimProfile": {"Width", "Depth"},
    "Shim": {"Thickness"},
    "SlotProfile": {"SlotWidth"},
    # Construction-only sketches, saved hidden, that locate the slot's radius
    # centre from the closed (+X) edge and the plan's lower (+Z) edge.  They
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
