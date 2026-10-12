r"""Rocker-arm drawing prose -- the manufacturing notes the part build stamps
into the SLDPRT and the isometric-view label.

Split OUT of ``rocker_arm_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_channel_assembly`` imports the rocker's
geometry, so drawing prose living in that import closure made every notes edit
full-rebuild ``assembly:ch_channel``.  Imported ONLY by ``build_rocker_arm`` and
the offline drawing test.
"""

from __future__ import annotations

from ch_rocker_arm_spec import STRAP_HUB_SYMMETRY

# The top edge's one-sided height over the pivot is a model dimension with
# its band on the part (rocker_arm_spec.TOP_EDGE_BAND, drawing-simplicity-policy.md `How the repository implements the guidelines`), so no
# note carries it. The hub is the other end of that chain: an OD off the bore
# axis by e lifts its top e toward the cheeks, and nothing else relates the two features. A
# plain note, not a frame (Main 2026-09-26); turning the hub and reaming the
# bore in one setup meets it without measuring. Its radius comes off the
# cheek-over-hub air in test_rocker_bank_layout.
HUB_COAXIALITY_DIA = 0.50


# True free-text instructions only; geometry / datum structure / roughness live
# in native dimensions / datum tags / FCFs / surface symbols. Hole process,
# size and through condition ride the native callouts; outline dimensions
# define the ends. BASIC radii and top height feed the arc-system profile
# frames directly.
# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_rocker_arm marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {"TopRadius", "BottomRadius", "RodTipLen"},
    "PivotHoleProfile": {"PivotDia"},
    "HubProfile": {"HubDia"},
    # #743 PR2: the hub length carries its +0.05/0 band natively; the 20-arm
    # stack acceptance (rocker_bank_layout) caps the sum.
    "Hub": {"HubLength"},
    # The top edge's height over the pivot axis, +0.50/0 natively (Codex #936
    # PRRT_kwDOPHDy386mV3AO). Only this one of the sketch's two dimensions
    # prints; the other places the line's foot on the pivot centre.
    "TopEdgeReference": {"TopAbovePivot"},
    # The strap thickness, +/-0.025 natively at three places (Main ruling
    # 2026-10, option b; ch_rocker_arm_spec.ARM_THICKNESS_BAND): the Strap
    # extrude's depth, printed in the end view where the section reads.
    "Strap": {"StrapThickness"},
}

# Decimal classes already authored by the part; shared with the offline
# requirement exporter. The remaining dimensions/notes print at two places.
DEFAULT_DRAWING_PRECISION = 2
DRAWING_PRECISION = {
    "Hub": {"HubLength": 3},
    "HubProfile": {"HubDia": DEFAULT_DRAWING_PRECISION},
    "TopEdgeReference": {"TopAbovePivot": DEFAULT_DRAWING_PRECISION},
    "Strap": {"StrapThickness": 3},
}

# BUILT_UP_PERMISSION_NOTE may be supplied only as exact explicit permission
# text in DRAWING_NOTES. None/absence means one_piece, never inferred permission.
BUILT_UP_PERMISSION_NOTE = None

DRAWING_NOTES = "\n".join(
    (
        # Outline dimensions and hole callouts carry geometry and process.
        "1. MIRROR-SYMMETRIC ABOUT THE PIVOT AXIS;",
        "   ROD-PIN HOLE (1X) AT THE END SHOWN.",
        "2. NOMINAL ARCS CONCENTRIC ON MIRROR AXIS.",
        # #948 ruling R: the rod's float on the arm is taken from the hub's
        # mid-plane, so the strap's offset from it is held.
        "3. STRAP SYMMETRIC TO HUB WITHIN "
        f"{STRAP_HUB_SYMMETRY:.{DEFAULT_DRAWING_PRECISION}f};",
        "   INTEGRAL HUB LENGTH SETS THE PITCH",
        "   (NO SPACERS). HUB OD COAXIAL WITH PIVOT",
        f"   BORE WITHIN Ø{HUB_COAXIALITY_DIA:.{DEFAULT_DRAWING_PRECISION}f} (TURN HUB AND REAM",
        "   BORE IN ONE SETUP).",
        # Source context: channel_kinematics.arc_geometry/solve_state and
        # build_ch_rocker_arm's chapter-30 profile reconstruction. The lower
        # arc is not a second amplitude-bar contact or independent gain control.
        "4. UPPER ARC: AMPLITUDE-BAR CONTACT.",
        "   LOWER ARC: MOVING STRAP ENVELOPE.",
        "   ROD-PIN SETS CONNECTING-ROD GEOMETRY.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
