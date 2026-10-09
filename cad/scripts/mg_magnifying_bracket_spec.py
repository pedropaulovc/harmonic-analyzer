r"""Magnifying-bracket dimensional contract -- the single source of truth shared
by the part build (``build_mg_magnifying_bracket.py``) and its manufacturing
drawing (``draw_mg_magnifying_bracket.py``).

PURE DATA, no SolidWorks/COM imports.  Nothing else imports this bracket's
nominals -- the magnifier assembly places it BY NAME and mates it by named
references (never a Python constant), so one ``_spec`` module is right here (no
``_geom`` split, unlike the magnifying LEVER whose knife-axis station an
assembly imports).  The offline lockstep test asserts the part marks and the
drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.

The bracket is a three-feature fitting: a revolved COLLAR tube (Ø12 OD, Ø6.2
bore, 10 long about local X), a rectangular ARM cantilevering +Z to the summing
plate, and a mounting FLANGE that butts the plate's front face.  The two plan
rectangles carry the auto-importable marked dimensions, including the flange
thickness band. Native counterbore callouts define the through bore and head
seat; the legacy collar dimensions and fit remain in the notes.
"""

from __future__ import annotations
from magnifying_bracket_joint_layout import (
    POSITION_BAND,
    GRIP_MIN,
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  Only the two extruded PLAN rectangles are marked (they auto-
# import to the top view exactly like column_clamp_front's BlockProfile); the
# arm and flange chains are NAME-DISAMBIGUATED in the build (ArmWidth/ArmDepth vs
# FlangeWidth/FlangeDepth) because a shared bare "Width"/"Depth" would collide in
# the top view's keep map. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArmProfile": {"ArmWidth", "ArmDepth"},
    "FlangeProfile": {"FlangeWidth", "FlangeDepth"},
    "Flange": {"FlangeHeight"},
    "MountingCoordinates": {"MountingX0", "MountingX1", "MountingY0"},
}

# Wizard callout precision is applied in the build through observed native
# dimension names; those identifiers must never be renamed for this contract.
DRAWING_PRECISION = {
    "ArmProfile": {"ArmWidth": 2, "ArmDepth": 2},
    "FlangeProfile": {"FlangeWidth": 2, "FlangeDepth": 3},
    "Flange": {"FlangeHeight": 2},
}
DRAWING_POSITION_BAND = POSITION_BAND

# True free-text instructions and the intentionally retained legacy collar
# dimensions. Mounting sizes and bands are native model/drawing dimensions.
DRAWING_NOTES = "\n".join(
    (
        "COLLAR Ø12 OD x 10 LONG (ALONG THE COLLAR AXIS), BORE Ø6.2 THRU -",
        "SLIP GUIDE ON THE Ø6 LEVER ROD.",
        "ARM 10 WIDE x 7.5 THICK.",
        "SEAT ON SUMMING-LEVER FRONT.",
        # Named exception: MHA-MG-001 counterbore floor 1.525 MIN
        # (drawing-simplicity-policy.md, "Named exceptions").
        f"COUNTERBORE FLOOR {GRIP_MIN:.3f} MIN.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
