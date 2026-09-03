r"""Connecting-rod dimensional contract -- the single source of truth shared by
the part build (``build_connecting_rod.py``) and its manufacturing drawing
(``draw_connecting_rod.py``).

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the pattern).
The nominal geometry here is imported by every builder/drawing consumer; the
marked-dimension -> kept map is the drift alarm the offline test enforces.
"""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# --- Nominal geometry (DIMENSIONS.md "Chapter 13 - Connecting rods"). ---
CENTER_DISTANCE = 163.1010299795349  # fixed-post recenter; level arm, plumb rod
RING_BORE_DIA = 30.8  # strap bore riding the eccentric cam
RING_BORE_DIA_BAND = (0.10, 0.00)  # running bore; (upper, lower) deviations
RING_WALL = 5.0  # radial strap wall
RING_THICKNESS = 3.0
SHANK_WIDTH = 8.0
SHANK_THICKNESS = 1.0
# Photo-backed upper joint (ch14 p.28 end views and page002_img02): a two-prong
# clevis owned by the rod captures the reduced 2.5 mm rocker tongue.  Dimensions
# are nominal because the slot and far cheek are occluded, but the topology,
# machine-front sign, and 7.0565 mm station-pitch envelope are unambiguous.  The
# flat shank is 1.0 mm thick at the root so its world-Z envelope clears the
# previous station's 4.9 mm clevis by 0.0565 mm.
PRONG_WIDTH_X = 8.0
PRONG_HEIGHT = 12.0
PRONG_CROWN_RADIUS = 4.0
PRONG_CROWN_CENTER_ABOVE_PIN = 2.0
PRONG_ROOT_BELOW_PIN = 6.0
PRONG_THICKNESS = 1.0
CLEVIS_SLOT_WIDTH = 2.9
CLEVIS_OUTSIDE_WIDTH = 2.0 * PRONG_THICKNESS + CLEVIS_SLOT_WIDTH  # 4.9
if abs(
    PRONG_HEIGHT
    - (
        PRONG_ROOT_BELOW_PIN
        + PRONG_CROWN_CENTER_ABOVE_PIN
        + PRONG_CROWN_RADIUS
    )
) > 1e-12:
    raise ValueError("D-cheek height must close root-to-pin, crown centre, and radius")
CLEVIS_CENTER_Z_LOCAL = -4.05  # after assembly Ry180: cam plane -> arm plane

# Local-Z envelopes.  "Near" is the cheek nearer the centred shank (local Z=0).
CLEVIS_Z_MIN = CLEVIS_CENTER_Z_LOCAL - CLEVIS_OUTSIDE_WIDTH / 2.0  # -6.50
CLEVIS_Z_MAX = CLEVIS_CENTER_Z_LOCAL + CLEVIS_OUTSIDE_WIDTH / 2.0  # -1.60
SLOT_Z_MIN = CLEVIS_CENTER_Z_LOCAL - CLEVIS_SLOT_WIDTH / 2.0  # -5.50
SLOT_Z_MAX = CLEVIS_CENTER_Z_LOCAL + CLEVIS_SLOT_WIDTH / 2.0  # -2.60
FAR_PRONG_Z_MIN = CLEVIS_Z_MIN
FAR_PRONG_Z_MAX = SLOT_Z_MIN
NEAR_PRONG_Z_MIN = SLOT_Z_MAX
NEAR_PRONG_Z_MAX = CLEVIS_Z_MAX

# A shallow U-bottom joins the cheeks across their full outside envelope.
# Its top overlaps the cheek roots by 0.5 mm.  A separate narrow offset neck
# overlaps both the near cheek and the centred shank by 0.5 mm in local Z.
CLEVIS_ROOT_OVERLAP = 0.5
CLEVIS_WEB_HEIGHT = 2.0
OFFSET_NECK_HEIGHT = 2.0
OFFSET_NECK_PRONG_OVERLAP = 0.5
OFFSET_NECK_SHANK_OVERLAP = 0.5
OFFSET_NECK_Z_MIN = NEAR_PRONG_Z_MAX - OFFSET_NECK_PRONG_OVERLAP  # -2.10
OFFSET_NECK_Z_MAX = -SHANK_THICKNESS / 2.0 + OFFSET_NECK_SHANK_OVERLAP  # -0.75
PIN_HOLE_DIA = 1.994  # rocker pin hole = #47 number drill

# --- Derived spans (mirror build_connecting_rod). ---
RING_OUTER_RADIUS = RING_BORE_DIA / 2.0 + RING_WALL  # 20.4
CLEVIS_CROWN_CENTER_Y = CENTER_DISTANCE + PRONG_CROWN_CENTER_ABOVE_PIN
CLEVIS_TOP_Y = CLEVIS_CROWN_CENTER_Y + PRONG_CROWN_RADIUS
CLEVIS_ROOT_Y = CENTER_DISTANCE - PRONG_ROOT_BELOW_PIN
CLEVIS_WEB_TOP_Y = CLEVIS_ROOT_Y + CLEVIS_ROOT_OVERLAP
CLEVIS_WEB_BOTTOM_Y = CLEVIS_WEB_TOP_Y - CLEVIS_WEB_HEIGHT
SHANK_END_Y = CLEVIS_ROOT_Y
RING_BOTTOM_Y = -RING_OUTER_RADIUS  # -20.4

SURFACE_FINISHES = (
    SurfaceFinishControl("strap_bore", MACHINED_UM, CylinderFace(RING_BORE_DIA)),
)


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_connecting_rod marks exactly these; draw_connecting_rod
# keeps exactly their union across its per-view ``keep`` maps. ---
# The marked-dimension contract moved to ``connecting_rod_notes`` with the rest
# of the drawing-only data (codex #354): it changes for drawing-only mark/keep
# updates, and ``build_channel_assembly`` imports this module.

# Drawing prose (DRAWING_NOTES / ISOMETRIC_VIEW_NOTE) lives in
# connecting_rod_notes.py so assemblies importing this spec never inherit a
# notes edit into their rebuild closure (codex #354).


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "rocker pin hole position": "0.20",
}
