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
    BOT_ARC_LEN,
    CENTER_Y,
    PIVOT_MID_Y,
    R_BOTTOM,
    R_TOP,
    TIP_FACE,
    TOP_ARC_LEN,
    HUB_DIA,
    PIVOT_HOLE_BAND,
)

# The amplitude bar's foot rides the top edge, and at d = 0 its cheeks pass
# over this arm's hub, so the print controls the edge's height over the pivot
# axis directly, on the mirror axis, one-sided: the edge may only come out
# high (user ruling 2026-09-26). The 808.00 centre distance is then REF, and
# the R800 governs only the curvature. With the amplitude bar's one-sided
# notch (amplitude_bar_notes.BOTTOM_NOTCH_DEPTH_BAND) a bar can rest at most
# 1.0 higher than nominal: a steady lever tilt of ~0.45 deg on that channel.
# Its fundamental moves at most 0.0036 mm (0.04 % of the d = 88 term) across
# the stations: error_budget.hook_displacement with the edge 0.5 high and the
# notch 0.5 shallow (test_rocker_bank_layout pins both numbers).
TOP_EDGE_ABOVE_PIVOT = CENTER_Y - PIVOT_MID_Y - R_TOP  # 8.0
TOP_EDGE_BAND = (0.50, 0.0)  # (upper, lower)
# The hub is the other end of that chain: an OD off the bore axis by e lifts
# its top e toward the cheeks, and nothing else relates the two features. A
# plain note, not a frame (Main 2026-09-26); turning the hub and reaming the
# bore in one setup meets it without measuring. Its radius comes off the
# cheek-over-hub air in test_rocker_bank_layout.
HUB_COAXIALITY_DIA = 0.50

# True free-text instructions only; geometry / datum structure / roughness live
# in native dimensions / datum tags / FCFs / surface symbols.  Hole sizes ride
# their native callouts (Ø6.50 dim, Ø1.99 THRU ALL) -- the notes state process,
# fit and count, never a second copy of a sheet dimension.  16.00 depth is a
# REF: it is fixed by the concentric R800/R816 edges.
# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_rocker_arm marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {"TopRadius", "BottomRadius"},
    "PivotHoleProfile": {"PivotDia"},
    # #743 PR2: the hub length carries its +0.05/0 band natively; the 20-arm
    # stack acceptance (rocker_bank_layout) caps the sum.
    "Hub": {"HubLength"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. PROFILE MIRROR-SYMMETRIC ABOUT THE",
        "   PIVOT-BORE AXIS; ROD-PIN HOLE AT ONE",
        "   END ONLY (1X), THE END SHOWN.",
        "2. STRAP 2.50 THICK; ALL HOLES THRU",
        "   THE THICKNESS.",
        f"3. TOP EDGE R{R_TOP:.2f}, BOTTOM EDGE R{R_BOTTOM:.2f},",
        "   CONCENTRIC; COMMON CENTRE ON THE",
        f"   MIRROR AXIS, {CENTER_Y - PIVOT_MID_Y:.2f} REF FROM THE PIVOT",
        f"   AXIS (STRAP DEPTH {ARM_DEPTH:.2f} REF).",
        # One-sided: the lower deviation is zero (rocker_arm_spec, tested).
        f"   TOP EDGE {TOP_EDGE_ABOVE_PIVOT:.2f} +{TOP_EDGE_BAND[0]:.2f}/0 ABOVE THE PIVOT",
        "   AXIS, ON THE MIRROR AXIS.",
        f"4. ARC LENGTHS {TOP_ARC_LEN:.2f} TOP / {BOT_ARC_LEN:.2f} BOTTOM",
        "   DEFINE THE ARC ENDPOINTS.",
        f"5. EACH END: {TIP_FACE:.2f} RADIAL LAND PERP TO",
        "   TOP EDGE; STRAIGHT TAPER TO BOTTOM ARC.",
        f"6. PIVOT HOLE: REAM +{PIVOT_HOLE_BAND[0]:.2f}/0, Ra 1.6.",
        f"7. INTEGRAL HUB DIA {HUB_DIA:.2f}, CENTRED ON THE",
        "   STRAP: THE HUBS SET THE STATION PITCH",
        "   (NO SPACERS). HUB OD COAXIAL WITH PIVOT",
        f"   BORE WITHIN Ø{HUB_COAXIALITY_DIA:.2f} (TURN HUB AND REAM",
        "   BORE IN ONE SETUP).",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
