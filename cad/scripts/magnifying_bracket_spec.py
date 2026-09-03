r"""Magnifying-bracket dimensional contract -- the single source of truth shared
by the part build (``build_magnifying_bracket.py``) and its manufacturing
drawing (``draw_magnifying_bracket.py``).

PURE DATA, no SolidWorks/COM imports.  Nothing else imports this bracket's
nominals -- the magnifier assembly places it BY NAME and mates it by named
references (never a Python constant), so one ``_spec`` module is right here (no
``_geom`` split, unlike the magnifying LEVER whose knife-axis station an
assembly imports).  The offline lockstep test asserts the part marks and the
drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.

The bracket is a three-feature fitting: a revolved COLLAR tube (Ø12 OD, Ø6.2
bore, 10 long about local X), a rectangular ARM cantilevering +Z to the summing
plate, and a mounting FLANGE that butts the plate's front face.  The nominals
below are the build's; the drawing reads them to aim its sheet picks (collar
silhouettes, flange tab, arm faces).
"""

from __future__ import annotations

# --- nominals (cad/DIMENSIONS.md ch. 20, M6.4, low) ---------------------------
COLLAR_OD = 12.0  # rod collar (low)
COLLAR_BORE = 6.2  # the O6 magnifying rod clamps in (derived)
COLLAR_HALF_LEN = 5.0  # along X
ARM_HALF_X = 5.0  # arm 10 wide (x), y -3..+4.5 (low)
ARM_Y = (-3.0, 4.5)
# DEPTH RE-ANCHOR (2026-07-04): the collar (part origin) moved forward with
# the lever rod (machine z -85 -> -128.3, ch30 p.4 plumb-wire re-anchor in
# build_magnifier_assembly), while the flange stays butted on the summing
# plate's UNCHANGED front face (machine -81..-76.45, north face 0.25 off the
# plate's -76.2). The arm therefore lengthens: local z 4 .. 58.3 = machine
# -124.3..-70 (same -70 end as before). The real black bracket cantilevers
# the rod well forward of the plate -- video 4/4 shows the rod extending from
# the pivoted summing bar over the wheel line.
ARM_Z = (4.0, 58.3)
FLANGE_X = (-20.0, 5.0)  # mounting flange, machine x +20..+45. The collar sits
# at machine x +40, EAST of the plate's east edge (+29.45), so the flange reaches
# WEST onto the plate front face: x +20..+29.45 (9.45 wide) butts it, the rest
# wraps the collar. (At -11 the flange stopped at x +29, touching the plate only at
# a 0.45-wide corner sliver -> it read as floating in the top view.) The west tab
# remains on the unchanged front-column/output side. The re-anchored channel
# spring bank now starts at z -64.012, still clear of this flange.
FLANGE_Y = (-2.54, 2.54)  # spans the plate's FULL height: with the collar/rod now
# at the plate centreline (machine 979.7, see build_magnifier_assembly LEVER_ROD_Y),
# the flange butts the plate FRONT FACE rather than tucking under it -- machine
# 977.16..982.24 = the coplanar .cs plate band
FLANGE_Z = (47.3, 51.85)  # SAME machine band as ever (-81..-76.45): north face
# at machine -76.45 = 0.25 south of the plate's real FRONT (-Z) face at -76.2
# (the plate is the Top-rect z +-76.2, centred on the pivot -- NOT -70, an
# earlier mis-read); the flange butts that face. Local values shifted by the
# 2026-07-04 depth re-anchor (collar/origin at machine -123.5, was -85); only
# the ARM between them lengthened.

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  Every station is measured from the collar axis (the part
# origin, one origin per view): the arm's far end (ArmCornerZ), the flange's
# far edge along the arm (FlangeCornerZ) and its far side across the arm
# (FlangeCornerX) locate the two plan rectangles, whose widths/depth ride the
# chain dims; the collar length is the revolve profile's WallLen.  ArmDepth
# (the arm's own 54.3) is NOT shown: its near end is buried inside the collar.
# The arm and flange chains are NAME-DISAMBIGUATED in the build
# (ArmWidth/ArmCornerZ vs FlangeWidth/FlangeDepth/...) because a shared bare
# "Width"/"Depth" would collide in the top view's keep map.  The collar
# diameters and the two Y thicknesses are drawing-added on real edges /
# silhouettes (a revolved tube gives no clean marked Ø). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"WallLen"},
    "ArmProfile": {"ArmWidth", "ArmCornerZ"},
    "FlangeProfile": {"FlangeWidth", "FlangeDepth", "FlangeCornerZ", "FlangeCornerX"},
}

# Notes (policy rule 6): the unmodelled mounting pattern is match-drilled at
# assembly, and the flange's Y position -- symmetric about the collar axis, a
# fact no single view dimension states cleanly -- is spelt out.  Every size is
# on a view.  No roughness: the bracket is lock-mated to the lever rod.
DRAWING_NOTES = "\n".join(
    (
        "MOUNTING HOLES: MATCH-DRILL TO THE SUMMING PLATE AT ASSEMBLY.",
        "FLANGE CENTRED ON THE COLLAR AXIS.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW"
