r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing."""

from __future__ import annotations


MM_PER_IN = 25.4

# Small black-steel clamp block on the swing platform that carries the axial
# end-play adjuster. See build_cone_tip_block.py for the derivation; this module
# is the drawing's single source of the marked dimensions.
BLOCK_X = 14.0  # plan width across the shaft
BLOCK_Z = 12.0  # plan depth along the shaft
BLOCK_HEIGHT = 55.0  # block height, foot to top
ADJUSTER_AXIS_HEIGHT = 47.65  # adjuster axis above the foot
ADJUSTER_THREAD = "5/16-18"  # blind tapped hole from the far (north) face
ADJUSTER_DEPTH = 8.0
PINCH_THREAD = "#3-48"  # cross-bore tapped hole that squeezes the top slit
PINCH_HEIGHT = 53.2
SLIT_W = 1.2  # top clamp slit width

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Width", "Depth"},
    "Block": {"BlockHt"},
    "SlitProfile": {"SlitW"},
}

DRAWING_NOTES = "\n".join(
    (
        "DATUM A IS FOOT SEAT.",
        f"ADJUSTER {ADJUSTER_THREAD} UNC-2B FROM REAR FACE; 6.00 MIN FULL THREAD;",
        "TAP-DRILL SHOULDER 8.00 +/-0.10 DEEP, STANDARD 118 DEG POINT.",
        "AXIS 47.65 +/-0.05 ABOVE A AND ON 14.00 WIDTH CENTERLINE +/-0.05;",
        "AXIS LIES IN A CYLINDRICAL ZONE DIA 0.05 PARALLEL TO DATUM A.",
        "REAR FACE IS RIGHT-HAND 14 X 55 FACE IN ISOMETRIC VIEW.",
        "DRILL DIA 2.946 +0.10/-0.00 NORMAL CLEARANCE THRU RIGHT-HAND JAW",
        f"ONLY IN FRONT VIEW; TAP {PINCH_THREAD} UNC-2B THRU LEFT-HAND JAW.",
        "PINCH AXIS 53.20 +/-0.05 ABOVE A; ON 12.00 DEPTH CENTERLINE +/-0.05.",
        "SLOT 1.20 +/-0.05 WIDE X 8.00 +/-0.10 DEEP THRU 12.00 DEPTH;",
        "BOTTOM R0.20 MAX; SLOT CENTERED ON 14.00 WIDTH CENTERLINE +/-0.05.",
    )
)
