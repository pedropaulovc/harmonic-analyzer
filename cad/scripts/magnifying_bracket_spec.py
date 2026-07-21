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
plate, and a mounting FLANGE that butts the plate's front face.  The two plan
rectangles (arm, flange) carry the auto-importable marked dimensions; the collar
diameters + bore, the through-thicknesses and the fit ride the notes (a revolved
tube gives no clean marked Ø, and its curved wall is not a dependable pick).
"""

from __future__ import annotations

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  Only the two extruded PLAN rectangles are marked (they auto-
# import to the top view exactly like column_clamp_front's BlockProfile); the
# arm and flange chains are NAME-DISAMBIGUATED in the build (ArmWidth/ArmDepth vs
# FlangeWidth/FlangeDepth) because a shared bare "Width"/"Depth" would collide in
# the top view's keep map. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArmProfile": {"ArmWidth", "ArmDepth"},
    "FlangeProfile": {"FlangeWidth", "FlangeDepth"},
}

# True free-text instructions only.  The collar OD/bore (a revolved tube has no
# clean marked Ø), the Y through-thicknesses (extrude depths, not sketch dims)
# and the slip fit on the Ø6 lever rod live here.  The part build stamps these
# strings into the SLDPRT; the drawing displays only $PRPSHEET links, so the
# print cannot silently diverge from its source model.
DRAWING_NOTES = "\n".join(
    (
        "COLLAR Ø12 OD, BORE Ø6.2 THRU x 10 LONG - SLIP GUIDE ON THE Ø6 LEVER ROD.",
        "ARM 10 WIDE x 7.5 THICK (Y); FLANGE 5 THICK (Y), BUTTS THE SUMMING-",
        "PLATE FRONT FACE. CURRENT PART IS AN UNDRILLED BLANK: MOUNTING-HOLE",
        "AXIS AND PATTERN ARE NOT DEFINED. DO NOT RELEASE UNTIL SPECIFIED.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
