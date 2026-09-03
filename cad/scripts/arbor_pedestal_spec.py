r"""Pure-data dimensional contract shared by the arbor-pedestal part and drawing.

The marked-dimension map lives here so a change rebuilds both the SLDPRT and the
SLDDRW recipes from one source (see build_arbor_pedestal.py for the geometry).
"""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

# Black japanned gray-iron bearing post that clamps the south end of the
# stationary cylinder arbor: a low rectangular foot flange, a tapered strap
# rising to a semicircular dome around the arbor clamp bore, and a #4 flange
# hold-down hole.
FOOT_WIDTH = 24.0  # X plan width of the foot flange
FOOT_DEPTH = 16.0  # Z plan depth of the foot flange
FOOT_HEIGHT = 5.0  # low flange height under the strap
STRAP_T = 10.0  # strap depth; far face is coplanar with the foot far face
TOP_RADIUS = 10.0  # dome radius = strap half-width at the top
DOME_DIA = 2.0 * TOP_RADIUS  # 20.0: the round head around the clamp bore
BORE_DIA = 0.375 * MM_PER_IN  # 9.525: the 3/8 in cylinder-arbor journal
BORE_DIA_BAND = (0.055, 0.025)  # running bore; (upper, lower) deviations
BORE_HEIGHT = 39.718  # v2 post journal axis: 6.35 platform + 33.368 boss height
SCREW_THREAD = "#4"  # flange hold-down clearance hole
# The #4 NORMAL clearance the wizard ACTUALLY cuts on this seat.
#
# 2026-07-26, settled against the wizard DATABASE rather than a build log.
# `diagnostics/diag_hole_wizard_tables.py` dumps the seat's own Screw Clearances
# table via ISldWorks::GetHoleStandardsData; the "#4" row reads
#
#     ['#4', '0.116', '0.1285', '0.136', ...]   # close / normal / loose, INCHES
#
# so normal fit is 0.1285 in = 3.2639 mm, matching _holes.CLEARANCE_MM's 3.264.
# A from-scratch rebuild the same day cut exactly that ("1x #4 clearance
# (Ø3.264)"), and HoleSpec.fit defaults to "normal", so the whole chain agrees.
#
# This pin was briefly 3.2512, read from an earlier build log. That value is NOT
# a "#4" entry in the seat's table OR in _holes.CLEARANCE_MM -- it is exactly
# ("#3", "loose") = 3.251. So the earlier reading was a wrong-size/fit
# resolution, not the seat's table moving, and pinning it baked a #3-loose-sized
# hole into a #4 clearance. Read the DATABASE, not the log line: the log echoes
# whatever was cut, so it cannot distinguish "the table says so" from "we asked
# for the wrong row".
#
# The guard that caught this worked exactly as written -- build_arbor_pedestal
# asserts the created hole matches this pin to 0.005 mm. It stayed silent for
# months only because part:arbor_pedestal was being restored from the remote
# cache; the first real rebuild after a _common.py change surfaced it at once.
# Kept as a literal rather than sourced from _holes.CLEARANCE_MM on purpose:
# this module is pure data with no imports, and pulling in _holes would drag
# _common/_telemetry into its dependency closure and re-key both the part and
# the drawing. The literal is instead pinned TO the resolver by
# `test_arbor_pedestal_drawing.test_screw_clearance_tracks_the_hole_resolver`,
# so the duplicate cannot drift again without a gate going red.
SCREW_CLEARANCE_DIA = 3.264

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "arbor_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_y_mm=BORE_HEIGHT),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FootProfile": {"Width", "Depth"},
    "Foot": {"FootHt"},
    # BoreHeight is recreated in the drawing between the actual datum-A foot
    # edge and the bore circle so its BASIC witness cannot collapse onto the
    # visually adjacent top of the flange.
    "BoreProfile": {"BoreDia"},
    "DomeProfile": {"DomeDia"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  The bore band rides
# the model dimension; the block Ra 3.2 covers every face but the bore.
DRAWING_NOTES = "\n".join(
    (
        "MACHINE FROM CONTINUOUS-CAST STOCK; REMOVE THE AS-CAST SKIN ALL OVER.",
        f"BORE RUNS ON THE DIA {BORE_DIA:.3f} CYLINDER ARBOR; BORE TO SIZE.",
        "HOLD-DOWN HOLE ON THE BORE CENTRELINE.",
        "JAPAN AFTER MACHINING; MASK THE BORE AND FOOT SEAT.",
    )
)
