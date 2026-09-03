r"""Knife-mount dimensional contract -- the single source of truth shared by the
part build (``build_knife_mount.py``) and its manufacturing drawing
(``draw_knife_mount.py``).

PURE DATA, no SolidWorks/COM imports.  Nothing else consumes this part's
nominals (no assembly imports ``build_knife_mount``), so one ``_spec`` module is
right here.  The block/bore geometry is derived in the build from the summing-
assembly layout; the fixed values are mirrored here for the drawing's view math,
and the offline lockstep test asserts the part marks and the drawing keeps
EXACTLY ``DRAWING_DIMENSIONS``.

NOTE on the "knife edge": this hardened-steel BEARING BLOCK (ch18 p.42,
2026-09-02 user re-read: unpainted heat-treated steel, not brass) carries a
circular bore CLOSE around the mating hex trunnion (Ø12 over the 8.653 x 10.268
hex), so only the trunnion's TOP VERTEX LINE nears the bore's upper inner wall
-- the true knife-edge line contact.  The sharp ridge is on the LEVER trunnion
(``build_summing_lever``), NOT on this part; this part's critical surface is the
bore's upper inner wall.  That is why the knife mount is on the GD&T allowlist
(cad/docs/drawing-simplicity-policy.md rule 3): the print keeps ONE position
frame on the bore to the top-seat datum and a ground finish on the bore, and
nothing else.
"""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import GROUND_UM, SurfaceFinishControl

# --- fixed geometry for the drawing's view math (mirrors build_knife_mount) ----
R_BORE = 6.0  # Ø12 knife-bearing bore (2026-09-02 ch18 p.42 re-read: close bore)
BLK_HALF_X = 12.0  # block half-width (24 across)
SUPPORT_Z_THICK = 14.0  # axial depth straddling the trunnion mid
BLK_TOP = 14.62  # local block top (hangs 0.25 under the top-frame casting underside)
BLK_BOT = -14.75  # local block bottom (BORE_CY - R_BORE - 3.0 wall)
BORE_CY = -5.75  # bore centre below the ridge origin (TopClear 0.25 - R_BORE)
# 1/2-13 tap-drill diameter (27/64; mirrors ``_holes.TAP_DRILL_MM`` -- the spec
# pulls in NO COM module, and the offline test pins the two equal).  The
# drawing picks the hanger-stud tap's drawn circle at this radius.
STUD_TAP_DRILL_DIA = 10.716

# The bore's upper wall is the knife seat the trunnion rides: ground.
SURFACE_FINISHES = (
    SurfaceFinishControl("knife_bore", GROUND_UM, CylinderFace(2.0 * R_BORE)),
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The block depth (14) is added on the sheet across the right-view
# section. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockWidth", "BlockHeight"},
    # BoreCz was dropped from the print: the sketch dim measures the centre
    # from the invisible part origin, which sits 0.25 above the bore top -- on
    # the sheet it read as a (wrong) 12.45 bore radius (blind review round 2).
    # The centre height is a sheet-authored BASIC dimension from the datum-A
    # top seat (the position frame's reference), not a marked dimension.
    "BoreProfile": {"BoreDia"},
}

# Notes: three lines of process fact the views cannot show (policy rule 6).
# The tap rides its hole callout; the bore's finish rides its symbol; the bore
# height from the top seat is the basic dimension feeding the frame.
DRAWING_NOTES = "\n".join(
    (
        "THE LEVER TRUNNION RIDES THE BORE'S UPPER WALL.",
        "TAP-DRILL POINT BREAKS INTO THE BORE CROWN: ACCEPTED.",
        "HARDEN AND TEMPER TO 58-60 HRC AFTER MACHINING; LEAVE UNPAINTED.",
        "TWO BLOCKS USED, ONE PER TRUNNION.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"


# Manufacturing GD&T limits consumed by the part's drawing projection: the ONE
# allowlisted frame (knife-edge system).
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "knife-bore position": "0.20",
}
