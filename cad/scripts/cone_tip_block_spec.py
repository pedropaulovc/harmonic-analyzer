r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing."""

from __future__ import annotations


MM_PER_IN = 25.4

# Small black-steel clamp block on the swing platform that journals the cone
# shaft's 1/32 in tip. See build_cone_tip_block.py for the derivation; this
# module is the drawing's single source of the marked dimensions.
BLOCK_X = 14.0  # plan width across the shaft
BLOCK_Z = 12.0  # plan depth along the shaft
BLOCK_HEIGHT = 55.0  # block height, foot to top
BORE_DIA = 0.03125 * MM_PER_IN  # 0.79375: the cone shaft's 1/32 in tip journal
BORE_HEIGHT = 47.65  # tip-journal axis above the foot
ADJUSTER_THREAD = "5/16-18"  # blind tapped hole from the far (north) face
ADJUSTER_DEPTH = 8.0
PINCH_THREAD = "#3-48"  # cross-bore tapped hole that squeezes the top slit
PINCH_HEIGHT = 53.2
SLIT_W = 1.2  # top clamp slit width

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Width", "Depth"},
    "Block": {"BlockHt"},
    "BoreProfile": {"BoreZ", "BoreDiaDim"},
    "SlitProfile": {"SlitW"},
}

DRAWING_NOTES = "\n".join(
    (
        "HEIGHTS ARE AXIS-TO-FOOT SEAT (DATUM A).",
        "JOURNAL, ADJUSTER + SLIT CENTERED ON THE 14 WIDTH.",
        "TIP JOURNAL DIA 0.794 (1/32 IN) THRU: REAM STRAIGHT TO A CLOSE",
        "  RUNNING FIT ON THE MATING CONE-SHAFT TIP; DEBURR LIGHTLY.",
        f"ADJUSTER HOLE {ADJUSTER_THREAD} UNC-2B TAPPED 8 FULL-THREAD DEEP",
        "  FROM THE REAR FACE, COAXIAL W/ THE JOURNAL WITHIN 0.1.",
        f"PINCH HOLE {PINCH_THREAD} UNC-2B TAPPED THRU, AXIS 53.2 ABOVE FOOT,",
        "  ACROSS THE TOP SLIT (1.2 WIDE X 8 DEEP) -- LOCKS THE ADJUSTER.",
        "MATERIAL AISI 1018 STEEL; BLACK OXIDE AFTER MACHINING.",
    )
)
