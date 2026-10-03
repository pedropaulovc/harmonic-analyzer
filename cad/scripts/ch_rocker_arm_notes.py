r"""Rocker-arm drawing prose -- the manufacturing notes the part build stamps
into the SLDPRT and the isometric-view label.

Split OUT of ``rocker_arm_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_channel_assembly`` imports the rocker's
geometry, so drawing prose living in that import closure made every notes edit
full-rebuild ``assembly:ch_channel``.  Imported ONLY by ``build_rocker_arm`` and
the offline drawing test.
"""

from __future__ import annotations

from ch_rocker_arm_spec import (
    ARM_DEPTH,
    ARM_THICKNESS,
    BOT_ARC_LEN,
    CENTER_Y,
    PIVOT_MID_Y,
    R_BOTTOM,
    R_TOP,
    TIP_FACE,
    TOP_ARC_LEN,
    HUB_DIA,
)

# The top edge's one-sided height over the pivot is a model dimension with
# its band on the part (ch_rocker_arm_spec.TOP_EDGE_BAND, policy rule 2), so no
# note carries it. The hub is the other end of that chain: an OD off the bore
# axis by e lifts its top e toward the cheeks, and nothing else relates the two features. A
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
# print shows.  build_ch_rocker_arm marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {"TopRadius", "BottomRadius"},
    "PivotHoleProfile": {"PivotDia"},
    # #743 PR2: the hub length carries its +0.05/0 band natively; the 20-arm
    # stack acceptance (rocker_bank_layout) caps the sum.
    "Hub": {"HubLength"},
    # The top edge's height over the pivot axis, +0.50/0 natively (Codex #936
    # PRRT_kwDOPHDy386mV3AO). Only this one of the sketch's two dimensions
    # prints; the other places the line's foot on the pivot centre.
    "TopEdgeReference": {"TopAbovePivot"},
}

# Decimal classes already authored by the part; shared with the offline
# requirement exporter. The remaining dimensions/notes print at two places.
DEFAULT_DRAWING_PRECISION = 2
DRAWING_PRECISION = {
    "Hub": {"HubLength": 3},
    "TopEdgeReference": {"TopAbovePivot": DEFAULT_DRAWING_PRECISION},
}

# BUILT_UP_PERMISSION_NOTE may be supplied only as exact explicit permission
# text in DRAWING_NOTES. None/absence means one_piece, never inferred permission.
BUILT_UP_PERMISSION_NOTE = None

DRAWING_NOTES = "\n".join(
    (
        # r743-3: the 21-line block rendered 0.76 over NOTES_CEILING; notes
        # 1-2 say the same in two fewer lines (test_ch_rocker_arm_drawing keeps a
        # full line of headroom at the measured pitch).
        "1. MIRROR-SYMMETRIC ABOUT THE PIVOT AXIS;",
        "   ROD-PIN HOLE (1X) AT THE END SHOWN.",
        f"2. STRAP {ARM_THICKNESS:.{DEFAULT_DRAWING_PRECISION}f} THICK; ALL HOLES THRU.",
        f"3. TOP EDGE R{R_TOP:.{DEFAULT_DRAWING_PRECISION}f}, "
        f"BOTTOM EDGE R{R_BOTTOM:.{DEFAULT_DRAWING_PRECISION}f},",
        "   CONCENTRIC; COMMON CENTRE ON THE",
        f"   MIRROR AXIS, {CENTER_Y - PIVOT_MID_Y:.{DEFAULT_DRAWING_PRECISION}f} REF FROM THE PIVOT",
        f"   AXIS (STRAP DEPTH {ARM_DEPTH:.{DEFAULT_DRAWING_PRECISION}f} REF).",
        f"4. ARC LENGTHS {TOP_ARC_LEN:.{DEFAULT_DRAWING_PRECISION}f} TOP / "
        f"{BOT_ARC_LEN:.{DEFAULT_DRAWING_PRECISION}f} BOTTOM",
        "   DEFINE THE ARC ENDPOINTS.",
        f"5. EACH END: {TIP_FACE:.{DEFAULT_DRAWING_PRECISION}f} RADIAL LAND PERP TO",
        "   TOP EDGE; STRAIGHT TAPER TO BOTTOM ARC.",
        # REAM is the fit bore's process requirement (policy rule 6); its
        # +0.03/0 band rides the O6.50 natively and its Ra the bore's symbol.
        "6. PIVOT HOLE: REAM.",
        f"7. INTEGRAL HUB DIA {HUB_DIA:.{DEFAULT_DRAWING_PRECISION}f}, CENTRED ON THE",
        "   STRAP: THE HUBS SET THE STATION PITCH",
        "   (NO SPACERS). HUB OD COAXIAL WITH PIVOT",
        f"   BORE WITHIN Ø{HUB_COAXIALITY_DIA:.{DEFAULT_DRAWING_PRECISION}f} (TURN HUB AND REAM",
        "   BORE IN ONE SETUP).",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
