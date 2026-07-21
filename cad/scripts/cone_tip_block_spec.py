r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing."""

from __future__ import annotations


MM_PER_IN = 25.4

# Small black-steel clamp block on the swing platform that journals the cone
# shaft's 1/32 in tip. See build_cone_tip_block.py for the derivation; this
# module is the drawing's single source of the marked dimensions.
BLOCK_X = 14.0  # plan width across the shaft
BLOCK_Z = 12.0  # plan depth along the shaft
BLOCK_HEIGHT = 55.0  # block height, foot to top
BORE_DIA = 0.819  # 0.814..0.824 finished bore over shaft max 0.794
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
        "DATUM A IS FOOT SEAT; DATUM B IS TIP-JOURNAL AXIS.",
        "JOURNAL BORE LIMITS DIA 0.814-0.824; AXIS 47.65 +/-0.05 ABOVE A.",
        "MATING SHAFT LIMITS DIA 0.774-0.794.",
        "JOURNAL, ADJUSTER + SLIT CENTERED ON 14.00 WIDTH WITHIN 0.05.",
        f"ADJUSTER HOLE {ADJUSTER_THREAD} UNC-2B FROM REAR FACE; 6.00 MIN",
        "FULL THREAD, TAP-DRILL SHOULDER 8.00 +/-0.10 DEEP WITH STANDARD",
        "118 DEG POINT. AXIS POSITION WITHIN DIA 0.05 TO B.",
        "REAR FACE IS RIGHT-HAND 14 X 55 FACE IN ISOMETRIC VIEW.",
        f"FROM RIGHT SIDE OF FRONT VIEW, DRILL {PINCH_THREAD} NORMAL CLEARANCE",
        f"THROUGH NEAR JAW ONLY; TAP {PINCH_THREAD} UNC-2B THRU FAR JAW.",
        "PINCH AXIS 53.20 +/-0.05 ABOVE A AND CENTERED IN 12.00 DEPTH",
        "WITHIN 0.05. SLOT 1.20 +/-0.05 WIDE X 8.00 +/-0.10 DEEP,",
        "THRU 12.00 DEPTH; BOTTOM R0.20 MAX.",
    )
)
