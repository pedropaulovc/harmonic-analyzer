r"""Rocker-arm drawing prose -- the manufacturing notes the part build stamps
into the SLDPRT and the isometric-view label.

Split OUT of ``rocker_arm_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_channel_assembly`` imports the rocker's
geometry, so drawing prose living in that import closure made every notes edit
full-rebuild ``assembly:channel``.  Imported ONLY by ``build_rocker_arm`` and
the offline drawing test.
"""

from __future__ import annotations

from rocker_arm_spec import (
    ARM_DEPTH,
    ARM_THICKNESS,
    BOT_ARC_LEN,
    CENTER_Y,
    PIVOT_MID_Y,
    R_BOTTOM,
    R_TOP,
    ROD_STEP_FROM_PIN,
    ROD_TONGUE_BEYOND_PIN,
    ROD_TONGUE_DEPTH,
    TAIL_TIP_FACE,
    TOP_ARC_LEN,
    HUB_DIA,
    HUB_LENGTH,
)

# True free-text instructions only; geometry / datum structure / roughness live
# in native dimensions / datum tags / FCFs / surface symbols.  Hole sizes ride
# their native callouts.  The notes make the asymmetric tail-versus-clevis
# boundary explicit because the front profile no longer mirrors about the pivot.
# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_rocker_arm marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {"TopRadius", "BottomRadius"},
    "PivotHoleProfile": {"PivotDia"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. PROFILE IS ASYMMETRIC ABOUT THE PIVOT;",
        "   ROD-PIN HOLE AT THE REDUCED END SHOWN (1X).",
        "2. STRAP 2.50 THICK; ALL HOLES THRU",
        "   THE THICKNESS.",
        f"3. TOP EDGE R{R_TOP:.2f}, BOTTOM EDGE R{R_BOTTOM:.2f},",
        "   CONCENTRIC; COMMON CENTRE ON THE",
        f"   PIVOT AXIS, {CENTER_Y - PIVOT_MID_Y:.2f} FROM THE PIVOT",
        f"   AXIS (STRAP DEPTH {ARM_DEPTH:.2f} REF).",
        f"4. TAIL MASTER SPANS {TOP_ARC_LEN:.2f} TOP / {BOT_ARC_LEN:.2f}",
        "   BOTTOM DEFINE THE TAIL ARC ENDPOINTS.",
        f"5. TAIL ONLY: {TAIL_TIP_FACE:.2f} RADIAL LAND PERP TO",
        "   TOP EDGE; STRAIGHT TAPER TO BOTTOM ARC.",
        f"6. ROD END: SQUARE SHOULDER {ROD_STEP_FROM_PIN:.2f} BEFORE PIN;",
        f"   TONGUE {ROD_TONGUE_DEPTH:.2f} DEEP, CENTRED ON PIN,",
        f"   SQUARE FREE FACE {ROD_TONGUE_BEYOND_PIN:.2f} BEYOND PIN.",
        "7. PIVOT HOLE: REAM +0.03/0, Ra 1.6.",
        f"8. INTEGRAL HUB DIA {HUB_DIA:.2f} X {HUB_LENGTH:.2f} ON THE PIVOT",
        f"   BORE, PROUD {(HUB_LENGTH - ARM_THICKNESS) / 2.0:.2f} EACH FACE;",
        "   HUBS SET STATION PITCH (NO SPACERS).",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
