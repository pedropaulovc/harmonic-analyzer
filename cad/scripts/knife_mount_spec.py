r"""Knife-mount dimensional contract -- the single source of truth shared by the
part build (``build_knife_mount.py``) and its manufacturing drawing
(``draw_knife_mount.py``).

PURE DATA, no SolidWorks/COM imports.  Nothing else consumes this part's
nominals (no assembly imports ``build_knife_mount``), so one ``_spec`` module is
right here.  The block/bore geometry is derived in the build from the summing-
assembly layout; the fixed values are mirrored here for the drawing's view math,
and the offline lockstep test asserts the part marks and the drawing keeps
EXACTLY ``DRAWING_DIMENSIONS``.

NOTE on the "knife edge": this brass BEARING BLOCK carries a circular bore MUCH
larger than the mating hex trunnion, so only the trunnion's TOP VERTEX LINE nears
the bore's upper inner wall -- the true knife-edge line contact.  The sharp ridge
is on the LEVER trunnion (``build_summing_lever``), NOT on this part; this part's
critical surface is the bore's upper inner wall, whose roundness/finish is called
out in the notes.
"""

from __future__ import annotations

# --- fixed geometry for the drawing's view math (mirrors build_knife_mount) ----
R_BORE = 12.7  # Ø25.4 knife-bearing bore
BLK_HALF_X = 17.0  # block half-width (34 across)
SUPPORT_Z_THICK = 14.0  # axial depth straddling the trunnion mid
BLK_TOP = 14.62  # local block top (abuts the top-crossbar lower face)
BLK_BOT = -29.15  # local block bottom
BORE_CY = -12.45  # bore centre below the ridge origin (TopClear - R_BORE)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The block depth (14) is added on the sheet across the right-view
# section. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockWidth", "BlockHeight"},
    # BoreCz was dropped from the print: the sketch dim measures the centre
    # from the invisible part origin, which sits 0.25 above the bore top -- on
    # the sheet it read as a (wrong) 12.45 bore radius (blind review round 2).
    # The centre height rides the notes, stated from the datum-A top seat.
    "BoreProfile": {"BoreDia"},
}

DRAWING_NOTES = "\n".join(
    (
        "BORE Ø25.4 THRU, CENTRED IN THE 34.00 WIDTH (ON THE BLOCK VERTICAL",
        f"CENTRELINE), CENTRE {BLK_TOP - BORE_CY:.2f} BELOW THE TOP SEAT",
        "(DATUM A). THE BORE IS THE KNIFE-EDGE BEARING: THE LEVER TRUNNION",
        "RIDES ITS UPPER INNER WALL. TWO BLOCKS USED, ONE PER TRUNNION.",
        "THE CURRENT MODEL HAS NO HARDENED KNIFE SEAT OR MOUNT-TO-CROSSBAR",
        "HOLES. SEAT MATERIAL, GEOMETRY, RETENTION, AND MOUNTING PATTERN ARE",
        "NOT DEFINED. DO NOT RELEASE UNTIL THOSE DETAILS ARE SPECIFIED.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
