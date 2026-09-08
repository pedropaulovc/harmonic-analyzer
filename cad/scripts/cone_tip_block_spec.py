r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing."""

from __future__ import annotations

from build_cone_tip_adjuster import CUP_DIA as SHAFT_PASSAGE_DIA


MM_PER_IN = 25.4

# Small black-steel clamp block on the swing platform that carries the axial
# end-play adjuster. See build_cone_tip_block.py for the derivation; this module
# is the drawing's single source of the marked dimensions.
BLOCK_X = 14.0  # plan width across the shaft
BLOCK_Z = 12.0  # plan depth along the shaft
BLOCK_HEIGHT = 40.718  # v2 post cascade: preserve the 1.000-mm crown above slit
BLOCK_HEIGHT_BAND = (0.05, 0.00)  # (upper, lower) deviations
ADJUSTER_AXIS_HEIGHT = 33.368  # coaxial with cone-pivot-post-v2 journal
ADJUSTER_THREAD = "5/16-18"  # blind tapped hole from the far (north) face
ADJUSTER_DEPTH = 8.0
# Non-bearing clearance passage from the south face into the adjuster bore. Its
# diameter matches the already-defined adjuster cup, so the shaft tip has one
# continuous envelope without reviving the removed fictional journal fit.
PINCH_THREAD = "#4-40"  # cross-bore tapped hole that squeezes the top slit
PINCH_HEIGHT = 38.918
PINCH_CLEARANCE_DIA = 3.264
SLIT_W = 1.2  # top clamp slit width
SLIT_DEPTH = 8.0  # slit cut down from the top face to 32.718

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Width", "Depth"},
    "Block": {"BlockHt"},
    "PassageProfile": {"PassageDiaDim", "PassageZ"},
    "PinchBore": {"PinchZ"},
    "SlitProfile": {"SlitW"},
}

DRAWING_NOTES = "\n".join(
    (
        f"DATUM A IS FOOT SEAT; B IS {BLOCK_X:.0f} WIDTH MEDIAN PLANE;",
        f"C IS ADJUSTER-ENTRY FACE; D IS {BLOCK_Z:.0f} DEPTH MEDIAN PLANE;",
        "E IS +X PINCH-ENTRY FACE IDENTIFIED IN FRONT + RIGHT VIEWS.",
        f"ADJUSTER {ADJUSTER_THREAD} UNC-2B FROM C; 6.00 MIN AXIAL",
        "FULL-FORM THREAD EACH JAW; INTERRUPTION BY SLOT IS INTENTIONAL;",
        f"TAP-DRILL SHOULDER {ADJUSTER_DEPTH:.2f} +/-0.10 DEEP, STANDARD 118 DEG POINT.",
        f"SHAFT CLEARANCE PASSAGE DIA {SHAFT_PASSAGE_DIA:.2f} THRU; MACHINE",
        "PASSAGE + ADJUSTER TAP IN ONE SETUP FROM C; APPLY POSITION",
        "FRAME TO BOTH COAXIAL FEATURES AS A SIMULTANEOUS REQUIREMENT;",
        "PASSAGE IS NOT A SHAFT-BEARING SURFACE.",
        f"DRILL DIA {PINCH_CLEARANCE_DIA:.3f} +0.10/-0.00 FROM E FACE TO SLOT;",
        f"IN SAME SETUP TAP {PINCH_THREAD} UNC-2B THRU OPPOSITE JAW; APPLY",
        "POSITION FRAME TO BOTH COAXIAL FEATURES AS A SIMULTANEOUS REQT.",
        "PINCH FEATURE MAY OPEN INTO TOP SLOT; 0.25 MIN TOP LIGAMENT.",
        # The 38.918/33.368 axis stack gives the #4 normal-clearance passage a
        # 0.05 nominal intersection with the adjuster thread crest
        # (3.264/2 + 7.938/2 - 5.55). The passage still cannot reach below the
        # crest band (0.32 nominal to the pitch cylinder), so the local crest
        # graze is intentional.
        "PASSAGE INTERSECTS ADJUSTER THREAD CREST 0.05 NOM; LOCAL CREST GRAZE",
        "BY PASSAGE IS PERMITTED; PASSAGE CANNOT CUT BELOW CREST BAND",
        "WITHIN STATED TOLS (0.32 NOM TO PITCH CYL); THREAD MUST GAGE 2B.",
        f"SLOT {SLIT_W:.2f} +/-0.05 WIDE X {SLIT_DEPTH:.2f} +/-0.10 DEEP THRU {BLOCK_Z:.2f} DEPTH;",
        "BOTTOM R0.20 MAX; SLOT MEDIAN PLANE BASIC 0 TO DATUM B;",
        "POSITION TOLERANCE 0.10 TO B IS THE TOTAL MEDIAN-PLANE ZONE.",
    )
)


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "adjuster common-axis true position": "0.05",
    "slot median-plane position": "0.10",
    "pinch common-axis true position": "0.05",
}
